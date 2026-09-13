use std::sync::OnceLock;
use std::time::Instant;

#[inline]
pub fn read_ticks() -> u64 {
    static EPOCH: OnceLock<Instant> = OnceLock::new();
    EPOCH.get_or_init(Instant::now).elapsed().as_nanos() as u64
}

pub fn timer_frequency_hz() -> Option<u64> {
    Some(1_000_000_000)
}

pub fn timer_name() -> &'static str {
    "portable monotonic clock"
}
