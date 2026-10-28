//! One blocking Hyprland event socket, one thread, updates only on state changes.
use serde::{Deserialize, de::DeserializeOwned};
use std::collections::HashMap;
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::raw::{c_int, c_uint, c_void};
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::thread;
use std::time::{Duration, Instant};

const OCCUPIED: u8 = 1;
const ACTIVE: u8 = 2;
const URGENT: u8 = 4;
const UNAVAILABLE: u8 = 8;
const IPC_TIMEOUT: Duration = Duration::from_secs(2);
const MAX_REPLY: usize = 16 * 1024 * 1024;
const MAX_EVENT: usize = 256 * 1024;

unsafe extern "C" {
    fn umask(mask: c_uint) -> c_uint;
    fn __libc_current_sigrtmin() -> c_int;
    fn pidfd_open(pid: c_int, flags: c_uint) -> c_int;
    fn pidfd_send_signal(fd: c_int, signal: c_int, info: *const c_void, flags: c_uint) -> c_int;
}

fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}

struct Ipc {
    directory: PathBuf,
}

impl Ipc {
    fn from_env() -> io::Result<Self> {
        let runtime =
            env::var_os("XDG_RUNTIME_DIR").ok_or_else(|| invalid("XDG_RUNTIME_DIR is unset"))?;
        let instance = env::var_os("HYPRLAND_INSTANCE_SIGNATURE")
            .ok_or_else(|| invalid("HYPRLAND_INSTANCE_SIGNATURE is unset"))?;
        Ok(Self {
            directory: PathBuf::from(runtime).join("hypr").join(instance),
        })
    }

    fn request(&self, command: &str) -> io::Result<Vec<u8>> {
        let deadline = Instant::now() + IPC_TIMEOUT;
        let mut connection = UnixStream::connect(self.directory.join(".socket.sock"))?;
        connection.set_write_timeout(Some(IPC_TIMEOUT))?;
        connection.write_all(command.as_bytes())?;
        let mut response = Vec::with_capacity(4096);
        let mut chunk = [0; 16 * 1024];
        loop {
            let remaining = deadline
                .checked_duration_since(Instant::now())
                .filter(|d| !d.is_zero())
                .ok_or_else(|| io::Error::new(io::ErrorKind::TimedOut, "Hyprland IPC timed out"))?;
            connection.set_read_timeout(Some(remaining))?;
            match connection.read(&mut chunk) {
                Ok(0) => return Ok(response),
                Ok(count) => {
                    if response.len() + count > MAX_REPLY {
                        return Err(invalid("Hyprland IPC reply exceeds 16 MiB"));
                    }
                    response.extend_from_slice(&chunk[..count]);
                }
                Err(e) if e.kind() == io::ErrorKind::Interrupted => continue,
                Err(e) => return Err(e),
            }
        }
    }

    fn query<T: DeserializeOwned>(&self, command: &str) -> io::Result<T> {
        serde_json::from_slice(&self.request(command)?).map_err(|e| invalid(e.to_string()))
    }

    fn focus(&self, number: u8) -> io::Result<u8> {
        let response = self.request(&format!(
            "/dispatch hl.dsp.focus({{ workspace = {number} }})"
        ))?;
        let mut stdout = io::stdout().lock();
        stdout.write_all(&response)?;
        if !response.ends_with(b"\n") {
            stdout.write_all(b"\n")?;
        }
        Ok(if response.starts_with(b"ok") { 0 } else { 1 })
    }
}

#[derive(Deserialize)]
struct Workspace {
    id: i64,
    windows: i64,
}

#[derive(Deserialize)]
struct WorkspaceId {
    id: i64,
}

#[derive(Deserialize)]
struct Client {
    address: String,
    workspace: WorkspaceId,
    #[serde(default)]
    urgent: bool,
}

fn occupied(workspaces: &[Workspace]) -> [bool; 9] {
    let mut result = [false; 9];
    for workspace in workspaces {
        if (1..=9).contains(&workspace.id) && workspace.windows > 0 {
            result[workspace.id as usize - 1] = true;
        }
    }
    result
}

fn address(value: &str) -> &str {
    value.strip_prefix("0x").unwrap_or(value)
}

#[derive(Default)]
struct State {
    occupied: [bool; 9],
    active: Option<i64>,
    urgent: HashMap<String, i64>,
}

impl State {
    fn snapshot(&mut self, ipc: &Ipc) -> io::Result<()> {
        self.refresh(ipc)?;
        self.active = Some(ipc.query::<WorkspaceId>("j/activeworkspace")?.id);
        self.urgent = ipc
            .query::<Vec<Client>>("j/clients")?
            .into_iter()
            .filter(|c| c.urgent)
            .map(|c| (address(&c.address).to_owned(), c.workspace.id))
            .collect();
        Ok(())
    }

    fn refresh(&mut self, ipc: &Ipc) -> io::Result<()> {
        self.occupied = occupied(&ipc.query::<Vec<Workspace>>("j/workspaces")?);
        Ok(())
    }

    fn output(&mut self) -> [u8; 9] {
        self.urgent
            .retain(|_, workspace| Some(*workspace) != self.active);
        std::array::from_fn(|i| {
            let number = i as i64 + 1;
            let mut flags = if self.occupied[i] { OCCUPIED } else { 0 };
            if self.active == Some(number) {
                flags |= ACTIVE;
            } else if self.urgent.values().any(|&w| w == number) {
                flags |= URGENT;
            }
            flags
        })
    }

    fn event(&mut self, ipc: &Ipc, name: &str, payload: &str) -> io::Result<bool> {
        let parse = |text: &str| {
            text.parse::<i64>()
                .map_err(|_| invalid("Malformed workspace event ignored."))
        };
        match name {
            "workspacev2" => self.active = Some(parse(payload.split(',').next().unwrap_or(""))?),
            "focusedmonv2" => {
                let (_, workspace) = payload
                    .rsplit_once(',')
                    .ok_or_else(|| invalid("Malformed monitor event ignored."))?;
                self.active = Some(parse(workspace)?);
            }
            "urgent" => {
                let target = address(payload);
                for client in ipc.query::<Vec<Client>>("j/clients")? {
                    if address(&client.address) == target {
                        self.urgent.insert(target.to_owned(), client.workspace.id);
                        break;
                    }
                }
            }
            "closewindow" => {
                self.urgent.remove(address(payload));
            }
            "movewindowv2" => {
                let mut fields = payload.split(',');
                let target = address(fields.next().unwrap_or(""));
                let workspace = fields
                    .next()
                    .ok_or_else(|| invalid("Malformed move event ignored."))?;
                if let Some(current) = self.urgent.get_mut(target) {
                    *current = parse(workspace)?;
                }
            }
            "configreloaded" => self.snapshot(ipc)?,
            _ => {}
        }
        Ok(matches!(
            name,
            "createworkspacev2"
                | "destroyworkspacev2"
                | "moveworkspacev2"
                | "openwindow"
                | "closewindow"
                | "movewindowv2"
        ))
    }
}

fn render(number: usize, flags: u8) -> String {
    let classes = if flags & UNAVAILABLE != 0 {
        "\"workspace\",\"unavailable\"".to_owned()
    } else {
        let mut classes = format!(
            "\"workspace\",\"{}\"",
            if flags & OCCUPIED != 0 {
                "occupied"
            } else {
                "empty"
            }
        );
        if flags & ACTIVE != 0 {
            classes.push_str(",\"active\"");
        } else if flags & URGENT != 0 {
            classes.push_str(",\"urgent\"");
        }
        classes
    };
    format!("{{\"text\":\"{number}\",\"class\":[{classes}]}}\n")
}

trait Publish {
    fn publish(&mut self, output: [u8; 9]) -> io::Result<()>;
}

struct Watch {
    number: usize,
    previous: Option<u8>,
}

impl Publish for Watch {
    fn publish(&mut self, output: [u8; 9]) -> io::Result<()> {
        let flags = output[self.number - 1];
        if self.previous != Some(flags) {
            let mut stdout = io::stdout().lock();
            stdout.write_all(render(self.number, flags).as_bytes())?;
            stdout.flush()?;
            self.previous = Some(flags);
        }
        Ok(())
    }
}

fn process_start(stat: &str) -> Option<&str> {
    stat.rsplit_once(") ")?.1.split_whitespace().nth(19)
}

fn waybar_process(directory: &Path) -> Option<File> {
    let text = fs::read_to_string(directory.join("bar.pid")).ok()?;
    let mut fields = text.split_whitespace();
    let pid: c_int = fields.next()?.parse().ok()?;
    let expected = fields.next()?;
    if pid <= 1 || fields.next().is_some() {
        return None;
    }
    // Open the pidfd BEFORE identity checks: a reused PID can never receive a signal.
    // SAFETY: positive pid and flags=0 follow the libc ABI.
    let fd = unsafe { pidfd_open(pid, 0) };
    if fd < 0 {
        return None;
    }
    // SAFETY: pidfd_open returns a fresh owned descriptor.
    let fd = unsafe { File::from_raw_fd(fd) };
    let process = PathBuf::from(format!("/proc/{pid}"));
    let stat = fs::read_to_string(process.join("stat")).ok()?;
    if process_start(&stat)? != expected
        || fs::read_to_string(process.join("comm")).ok()?.trim() != "waybar"
    {
        return None;
    }
    Some(fd)
}

struct Publisher {
    directory: PathBuf,
    previous: [Option<u8>; 9],
    ready: bool,
}

impl Publisher {
    fn new(directory: PathBuf) -> Self {
        Self {
            directory,
            previous: [None; 9],
            ready: false,
        }
    }

    fn notify(&self, changed: &[usize]) {
        if let Some(process) = waybar_process(&self.directory) {
            // SAFETY: this function returns glibc's current real-time signal base.
            let base = unsafe { __libc_current_sigrtmin() };
            for number in changed {
                // SAFETY: process is an owned pidfd; null info and flags=0 request a regular signal.
                unsafe {
                    pidfd_send_signal(
                        process.as_raw_fd(),
                        base + *number as c_int,
                        std::ptr::null(),
                        0,
                    )
                };
            }
        }
    }
}

impl Publish for Publisher {
    fn publish(&mut self, output: [u8; 9]) -> io::Result<()> {
        let mut changed = Vec::with_capacity(9);
        for (i, flags) in output.into_iter().enumerate() {
            if self.previous[i] == Some(flags) {
                continue;
            }
            let number = i + 1;
            let temporary = self.directory.join(format!("{number}.tmp"));
            fs::write(&temporary, render(number, flags))?;
            fs::rename(temporary, self.directory.join(format!("{number}.json")))?;
            self.previous[i] = Some(flags);
            changed.push(number);
        }
        if !changed.is_empty() {
            self.notify(&changed);
        }
        if !self.ready {
            OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(false)
                .open(self.directory.join("ready"))?;
            self.ready = true;
        }
        Ok(())
    }
}

fn event_session(ipc: &Ipc, publisher: &mut impl Publish) -> io::Result<()> {
    // Subscribe before the snapshot so changes during queries remain queued.
    let mut connection = UnixStream::connect(ipc.directory.join(".socket2.sock"))?;
    let mut state = State::default();
    state.snapshot(ipc)?;
    publisher.publish(state.output())?;
    let mut chunk = [0; 65536];
    let mut pending = Vec::with_capacity(8192);
    loop {
        let count = match connection.read(&mut chunk) {
            Ok(0) => {
                return Err(io::Error::new(
                    io::ErrorKind::UnexpectedEof,
                    "Hyprland event socket closed",
                ));
            }
            Ok(count) => count,
            Err(e) if e.kind() == io::ErrorKind::Interrupted => continue,
            Err(e) => return Err(e),
        };
        pending.extend_from_slice(&chunk[..count]);
        let mut refresh = false;
        let mut consumed = 0;
        for raw in pending.split_inclusive(|&b| b == b'\n') {
            if !raw.ends_with(b"\n") {
                break;
            }
            consumed += raw.len();
            let line = match std::str::from_utf8(&raw[..raw.len() - 1]) {
                Ok(line) if raw.len() <= MAX_EVENT => line,
                _ => {
                    eprintln!("Malformed workspace event ignored.");
                    continue;
                }
            };
            let Some((name, payload)) = line.split_once(">>") else {
                continue;
            };
            match state.event(ipc, name, payload) {
                Ok(needs_refresh) => refresh |= needs_refresh,
                Err(e) if e.kind() == io::ErrorKind::InvalidData => {
                    eprintln!("{e}");
                    continue;
                }
                Err(e) => return Err(e),
            }
            // Focus/urgency is visible before any window-count refresh in this batch.
            if matches!(name, "workspacev2" | "focusedmonv2" | "urgent") {
                publisher.publish(state.output())?;
            }
        }
        pending.drain(..consumed);
        if pending.len() > MAX_EVENT {
            return Err(invalid("Hyprland event exceeds 256 KiB"));
        }
        if refresh {
            state.refresh(ipc)?;
        }
        publisher.publish(state.output())?;
    }
}

fn events(ipc: &Ipc, publisher: &mut impl Publish) -> io::Result<u8> {
    loop {
        match event_session(ipc, publisher) {
            Err(e) if e.kind() == io::ErrorKind::BrokenPipe => return Ok(0),
            Err(e) => {
                eprintln!("Workspace status unavailable: {e}");
                publisher.publish([UNAVAILABLE; 9])?;
                thread::sleep(Duration::from_secs(2));
            }
            Ok(()) => unreachable!(),
        }
    }
}

fn run() -> io::Result<u8> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() == 1 && matches!(args[0].as_str(), "-h" | "--help") {
        println!("Usage: waybar-workspace serve | {{watch|status|focus}} <1-9>");
        return Ok(0);
    }
    let action = args.first().map(String::as_str).unwrap_or("");
    let number = args
        .get(1)
        .and_then(|n| n.parse::<u8>().ok())
        .filter(|n| (1..=9).contains(n));
    if !((action == "serve" && args.len() == 1)
        || (matches!(action, "watch" | "status" | "focus") && args.len() == 2 && number.is_some()))
    {
        eprintln!("Usage: waybar-workspace serve | {{watch|status|focus}} <1-9>");
        return Ok(2);
    }
    let ipc = Ipc::from_env()?;
    match action {
        "serve" => {
            // SAFETY: the program is single-threaded; mode 077 is valid.
            unsafe { umask(0o077) };
            let directory = env::var_os("WAYBAR_WORKSPACE_DIR")
                .ok_or_else(|| invalid("WAYBAR_WORKSPACE_DIR is unset"))?;
            events(&ipc, &mut Publisher::new(PathBuf::from(directory)))
        }
        "watch" => events(
            &ipc,
            &mut Watch {
                number: number.unwrap() as usize,
                previous: None,
            },
        ),
        "focus" => ipc.focus(number.unwrap()),
        "status" => {
            let workspaces = occupied(&ipc.query::<Vec<Workspace>>("j/workspaces")?);
            let active = ipc.query::<WorkspaceId>("j/activeworkspace")?.id;
            let number = number.unwrap() as usize;
            let flags = if workspaces[number - 1] { OCCUPIED } else { 0 }
                | if active == number as i64 { ACTIVE } else { 0 };
            io::stdout()
                .lock()
                .write_all(render(number, flags).as_bytes())?;
            Ok(0)
        }
        _ => unreachable!(),
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(e) if e.kind() == io::ErrorKind::BrokenPipe => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("Workspace status unavailable: {e}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renderer_matches_classes_and_precedence() {
        for flags in 0..16 {
            let value: serde_json::Value = serde_json::from_str(&render(3, flags)).unwrap();
            assert_eq!(value["text"], "3");
            let classes = value["class"].as_array().unwrap();
            assert_eq!(classes[0], "workspace");
            if flags & UNAVAILABLE != 0 {
                assert_eq!(classes.len(), 2);
                assert_eq!(classes[1], "unavailable");
            } else {
                assert_eq!(
                    classes[1],
                    if flags & OCCUPIED != 0 {
                        "occupied"
                    } else {
                        "empty"
                    }
                );
                assert_eq!(
                    classes.contains(&serde_json::json!("active")),
                    flags & ACTIVE != 0
                );
                assert_eq!(
                    classes.contains(&serde_json::json!("urgent")),
                    flags & ACTIVE == 0 && flags & URGENT != 0
                );
            }
        }
    }

    #[test]
    fn counts_ignore_special_workspaces_and_empty_ones() {
        let values = serde_json::from_str::<Vec<Workspace>>(r#"[{"id":-99,"windows":4},{"id":1,"windows":0},{"id":2,"windows":2},{"id":9,"windows":1},{"id":10,"windows":2}]"#).unwrap();
        assert_eq!(
            occupied(&values),
            [false, true, false, false, false, false, false, false, true]
        );
    }

    #[test]
    fn visiting_workspace_clears_urgency_permanently() {
        let mut state = State {
            active: Some(2),
            ..State::default()
        };
        state.urgent.insert("abc".into(), 1);
        state.urgent.insert("def".into(), 2);
        assert_eq!(state.output()[0], URGENT);
        assert_eq!(state.output()[1], ACTIVE);
        state.active = Some(1);
        assert_eq!(state.output()[0], ACTIVE);
        state.active = Some(3);
        assert_eq!(state.output()[0], 0);
        assert!(state.urgent.is_empty());
    }

    #[test]
    fn move_and_close_preserve_other_urgent_windows() {
        let ipc = Ipc {
            directory: PathBuf::new(),
        };
        let mut state = State::default();
        state.urgent.insert("abc".into(), 1);
        state.urgent.insert("def".into(), 1);
        assert!(
            state
                .event(&ipc, "movewindowv2", "0xabc,4,workspace,name")
                .unwrap()
        );
        assert_eq!(state.urgent["abc"], 4);
        assert!(state.event(&ipc, "closewindow", "abc").unwrap());
        assert_eq!(state.output()[0], URGENT);
        assert_eq!(state.output()[3], 0);
    }

    #[test]
    fn malformed_focus_does_not_change_state() {
        let ipc = Ipc {
            directory: PathBuf::new(),
        };
        let mut state = State {
            active: Some(1),
            ..State::default()
        };
        assert!(state.event(&ipc, "workspacev2", "invalid").is_err());
        assert!(state.event(&ipc, "focusedmonv2", "no-comma").is_err());
        assert_eq!(state.active, Some(1));
        state
            .event(&ipc, "focusedmonv2", "monitor,with,commas,9")
            .unwrap();
        assert_eq!(state.active, Some(9));
    }

    #[test]
    fn proc_stat_handles_spaces_and_parentheses_in_comm() {
        let fields = (3..=30)
            .map(|n| n.to_string())
            .collect::<Vec<_>>()
            .join(" ");
        assert_eq!(
            process_start(&format!("123 (name ) with spaces) {fields}")),
            Some("22")
        );
        assert_eq!(process_start("malformed"), None);
    }
}
