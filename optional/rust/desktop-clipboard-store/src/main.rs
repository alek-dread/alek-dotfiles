//! Short-lived Linux clipboard filter. No daemon, threads or third-party crates.

use std::env;
use std::fs::File;
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd, RawFd};
use std::os::raw::{c_int, c_short, c_uint};
use std::os::unix::process::ExitStatusExt;
use std::process::{Child, Command, ExitCode, Stdio};
use std::time::{Duration, Instant};

const MAX_ENTRY: usize = 5_000_000;
const READ_TIMEOUT: Duration = Duration::from_secs(5);
const STORE_TIMEOUT: Duration = Duration::from_secs(8);
const TIFF: [[u8; 4]; 4] = [*b"II*\0", *b"MM\0*", *b"II+\0", *b"MM\0+"];

// Linux libc ABI. pidfd_open requires glibc >= 2.36 and Linux >= 5.3.
const POLLIN: c_short = 0x001;
const POLLOUT: c_short = 0x004;
const POLLNVAL: c_short = 0x020;
const F_GETFL: c_int = 3;
const F_SETFL: c_int = 4;
const O_NONBLOCK: c_int = 0x800;

#[repr(C)]
struct PollFd {
    fd: c_int,
    events: c_short,
    revents: c_short,
}

unsafe extern "C" {
    fn poll(fds: *mut PollFd, nfds: usize, timeout: c_int) -> c_int;
    fn fcntl(fd: c_int, command: c_int, ...) -> c_int;
    fn umask(mask: c_uint) -> c_uint;
    fn pidfd_open(pid: c_int, flags: c_uint) -> c_int;
}

fn timed_out() -> io::Error {
    io::Error::new(io::ErrorKind::TimedOut, "clipboard transfer timed out")
}

fn wait_ready(fd: RawFd, events: c_short, deadline: Instant) -> io::Result<()> {
    loop {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .ok_or_else(timed_out)?;
        // Round up so a sub-millisecond remainder never becomes a busy loop.
        let timeout = remaining
            .as_millis()
            .saturating_add(1)
            .min(c_int::MAX as u128) as c_int;
        let mut descriptor = PollFd {
            fd,
            events,
            revents: 0,
        };
        // SAFETY: descriptor is a live, writable pollfd and nfds is exactly one.
        let result = unsafe { poll(&mut descriptor, 1, timeout) };
        if result > 0 {
            if descriptor.revents & POLLNVAL != 0 {
                return Err(io::Error::from_raw_os_error(9)); // EBADF
            }
            // HUP/ERR also wake us: read/write/wait obtains EOF or the actual error.
            return Ok(());
        }
        if result == 0 {
            return Err(timed_out());
        }
        let error = io::Error::last_os_error();
        if error.kind() != io::ErrorKind::Interrupted {
            return Err(error);
        }
    }
}

fn read_clipboard(
    input: &mut (impl Read + AsRawFd),
    limit: usize,
    deadline: Instant,
) -> io::Result<Option<Vec<u8>>> {
    let capacity_limit = limit + 1;
    let mut data = vec![0; capacity_limit.min(8192)];
    let mut filled = 0;
    loop {
        wait_ready(input.as_raw_fd(), POLLIN, deadline)?;
        match input.read(&mut data[filled..]) {
            Ok(0) => {
                data.truncate(filled);
                return Ok((filled != 0).then_some(data));
            }
            Ok(count) => {
                filled += count;
                if filled > limit || (filled >= 4 && TIFF.iter().any(|h| data.starts_with(h))) {
                    return Ok(None);
                }
                if filled == data.len() {
                    let next = (data.len() * 2).min(capacity_limit);
                    // Bound the allocation, including Vec's otherwise geometric spare capacity.
                    data.reserve_exact(next - data.len());
                    data.resize(next, 0);
                }
            }
            Err(error)
                if matches!(
                    error.kind(),
                    io::ErrorKind::Interrupted | io::ErrorKind::WouldBlock
                ) => {}
            Err(error) => return Err(error),
        }
    }
}

// Every error after spawn must terminate and reap ClipHist, including pipe errors.
struct ChildGuard(Child);

impl Drop for ChildGuard {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn store(data: &[u8], command: &mut Command, timeout: Duration) -> io::Result<u8> {
    let deadline = Instant::now() + timeout;
    let mut child = ChildGuard(
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?,
    );
    // SAFETY: the child PID is live and flags=0 is the documented pidfd_open ABI.
    let process_fd = unsafe { pidfd_open(child.0.id() as c_int, 0) };
    if process_fd < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: pidfd_open returned a fresh owned descriptor, closed by File's Drop.
    let process_fd = unsafe { File::from_raw_fd(process_fd) };
    let mut input = child
        .0
        .stdin
        .take()
        .ok_or_else(|| io::Error::other("missing child stdin"))?;
    let fd = input.as_raw_fd();
    // SAFETY: fd is an open pipe; these fcntl commands read/update its status flags.
    let flags = unsafe { fcntl(fd, F_GETFL) };
    if flags < 0 || unsafe { fcntl(fd, F_SETFL, flags | O_NONBLOCK) } < 0 {
        return Err(io::Error::last_os_error());
    }
    let mut remaining = data;
    while !remaining.is_empty() {
        wait_ready(fd, POLLOUT, deadline)?;
        match input.write(remaining) {
            Ok(0) => return Err(io::ErrorKind::WriteZero.into()),
            Ok(count) => remaining = &remaining[count..],
            // Match subprocess.communicate: an early close still reports the child status.
            Err(error) if error.kind() == io::ErrorKind::BrokenPipe => break,
            Err(error)
                if matches!(
                    error.kind(),
                    io::ErrorKind::Interrupted | io::ErrorKind::WouldBlock
                ) => {}
            Err(error) => return Err(error),
        }
    }
    drop(input); // EOF lets ClipHist finish reading and commit the entry.
    wait_ready(process_fd.as_raw_fd(), POLLIN, deadline)?;
    let status = child.0.wait()?;
    // Preserve the original Python wrapper's sys.exit(-signal) convention.
    Ok(status
        .code()
        .unwrap_or_else(|| -status.signal().unwrap_or(1)) as u8)
}

fn run() -> io::Result<u8> {
    // SAFETY: this short-lived program is single-threaded; mode 077 is valid.
    unsafe { umask(0o077) };
    if env::var_os("CLIPBOARD_STATE").as_deref() != Some(std::ffi::OsStr::new("data")) {
        return Ok(0);
    }
    // SAFETY: this program takes sole ownership of its inherited stdin descriptor.
    let mut input = unsafe { File::from_raw_fd(0) };
    let Some(data) = read_clipboard(&mut input, MAX_ENTRY, Instant::now() + READ_TIMEOUT)? else {
        return Ok(0);
    };
    store(
        &data,
        Command::new("/usr/bin/cliphist").arg("store"),
        STORE_TIMEOUT,
    )
}

fn main() -> ExitCode {
    // Keep stdout/stderr silent, as in the original helper.
    ExitCode::from(run().unwrap_or(1))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::net::UnixStream;
    use std::thread;

    fn read_bytes(data: Vec<u8>, limit: usize) -> Option<Vec<u8>> {
        let (mut reader, mut writer) = UnixStream::pair().unwrap();
        let producer = thread::spawn(move || {
            let _ = writer.write_all(&data);
        });
        let result =
            read_clipboard(&mut reader, limit, Instant::now() + Duration::from_secs(2)).unwrap();
        drop(reader);
        producer.join().unwrap();
        result
    }

    fn shell(script: &str) -> Command {
        let mut command = Command::new("/bin/sh");
        command.args(["-c", script]);
        command
    }

    #[test]
    fn preserves_exact_text_and_binary_bytes() {
        for data in [
            b"  \ttext\n\0".as_slice(),
            "Привет\n\u{2028}".as_bytes(),
            b"\x89PNG\r\n\x1a\nfixture",
            b"II*",
            b"M",
        ] {
            assert_eq!(read_bytes(data.to_vec(), MAX_ENTRY).unwrap(), data);
        }
    }

    #[test]
    fn rejects_empty_and_all_tiff_headers() {
        assert!(read_bytes(vec![], MAX_ENTRY).is_none());
        for header in TIFF {
            assert!(read_bytes([header.as_slice(), b"payload"].concat(), MAX_ENTRY).is_none());
        }
    }

    #[test]
    fn accepts_limit_and_rejects_one_extra_byte() {
        let data = vec![b'x'; MAX_ENTRY];
        assert_eq!(read_bytes(data, MAX_ENTRY).unwrap().len(), MAX_ENTRY);
        assert!(read_bytes(vec![b'x'; MAX_ENTRY + 1], MAX_ENTRY).is_none());
    }

    #[test]
    fn partial_header_is_checked_across_reads() {
        let (mut reader, mut writer) = UnixStream::pair().unwrap();
        let producer = thread::spawn(move || {
            writer.write_all(b"II").unwrap();
            thread::sleep(Duration::from_millis(20));
            writer.write_all(b"*\0").unwrap();
        });
        assert!(
            read_clipboard(
                &mut reader,
                MAX_ENTRY,
                Instant::now() + Duration::from_secs(2)
            )
            .unwrap()
            .is_none()
        );
        producer.join().unwrap();
    }

    #[test]
    fn rejects_oversize_without_waiting_for_eof() {
        let (mut reader, mut writer) = UnixStream::pair().unwrap();
        writer.write_all(b"123456789").unwrap();
        assert!(
            read_clipboard(&mut reader, 8, Instant::now() + Duration::from_millis(100))
                .unwrap()
                .is_none()
        );
    }

    #[test]
    fn incomplete_source_times_out() {
        let (mut reader, mut writer) = UnixStream::pair().unwrap();
        writer.write_all(b"unfinished").unwrap();
        let error = read_clipboard(
            &mut reader,
            MAX_ENTRY,
            Instant::now() + Duration::from_millis(30),
        )
        .unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
    }

    #[test]
    fn continuous_source_cannot_extend_deadline() {
        let (mut reader, mut writer) = UnixStream::pair().unwrap();
        let producer = thread::spawn(move || {
            while writer.write_all(b"x").is_ok() {
                thread::sleep(Duration::from_millis(2));
            }
        });
        let error = read_clipboard(
            &mut reader,
            MAX_ENTRY,
            Instant::now() + Duration::from_millis(30),
        )
        .unwrap_err();
        drop(reader);
        producer.join().unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
    }

    #[test]
    fn store_preserves_payload_and_delivers_eof() {
        let payload = b" \0\n\t\xffbinary\n";
        let mut command = shell(
            "exec /usr/bin/python3 -c 'import sys; sys.exit(0 if sys.stdin.buffer.read() == bytes.fromhex(sys.argv[1]) else 9)' \"$1\"",
        );
        let hex: String = payload.iter().map(|b| format!("{b:02x}")).collect();
        command.arg("test").arg(hex);
        assert_eq!(
            store(payload, &mut command, Duration::from_secs(2)).unwrap(),
            0
        );
    }

    #[test]
    fn store_handles_large_partial_writes() {
        assert_eq!(
            store(
                &vec![b'x'; MAX_ENTRY],
                &mut shell("exec /usr/bin/wc -c"),
                Duration::from_secs(2)
            )
            .unwrap(),
            0
        );
    }

    #[test]
    fn propagates_early_exit_status_and_signals() {
        for (script, expected) in [
            ("exit 7", 7),
            ("exec 0<&-; exit 0", 0),
            ("kill -TERM $$", 241),
        ] {
            assert_eq!(
                store(
                    &vec![0; 100_000],
                    &mut shell(script),
                    Duration::from_secs(2)
                )
                .unwrap(),
                expected
            );
        }
    }

    #[test]
    fn blocked_child_input_times_out_and_is_reaped() {
        let error = store(
            &vec![0; MAX_ENTRY],
            &mut shell("exec /usr/bin/sleep 30"),
            Duration::from_millis(40),
        )
        .unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
    }

    #[test]
    fn child_exit_after_eof_has_same_deadline() {
        let error = store(
            b"x",
            &mut shell("exec /usr/bin/sleep 30"),
            Duration::from_millis(40),
        )
        .unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
    }

    #[test]
    fn guard_terminates_and_reaps_child() {
        let guard = ChildGuard(Command::new("/usr/bin/sleep").arg("30").spawn().unwrap());
        let pid = guard.0.id();
        drop(guard);
        assert!(!std::path::Path::new(&format!("/proc/{pid}")).exists());
    }

    #[test]
    fn spawn_failure_is_reported() {
        assert!(
            store(
                b"x",
                &mut Command::new("/nonexistent/cliphist"),
                Duration::from_secs(1)
            )
            .is_err()
        );
    }
}
