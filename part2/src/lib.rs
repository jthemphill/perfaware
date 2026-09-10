mod profiler;

pub use profiler::{ProfilerStats, TickCounter};

// X86

#[cfg(target_arch = "x86_64")]
#[inline]
pub fn read_ticks() -> u64 {
    unsafe { core::arch::x86_64::_rdtsc() }
}

#[cfg(target_arch = "x86_64")]
pub fn timer_frequency_hz() -> Option<u64> {
    use core::arch::x86_64::__cpuid;

    unsafe {
        // Check the highest supported basic CPUID leaf.
        if __cpuid(0).eax < 0x15 {
            return None;
        }

        let info = __cpuid(0x15);
        if info.eax == 0 || info.ebx == 0 || info.ecx == 0 {
            return None;
        }

        Some(u64::from(info.ecx) * u64::from(info.ebx) / u64::from(info.eax))
    }
}

// ARM

#[cfg(target_arch = "aarch64")]
#[inline]
pub fn read_ticks() -> u64 {
    let ticks: u64;
    unsafe {
        core::arch::asm!(
            "mrs {ticks}, cntvct_el0",
            ticks = out(reg) ticks,
            options(nomem, nostack, preserves_flags),
        );
    }
    ticks
}

#[cfg(target_arch = "aarch64")]
#[inline]
pub fn timer_frequency_hz() -> Option<u64> {
    let freq: u64;
    unsafe {
        core::arch::asm!(
            "mrs {freq}, cntfrq_el0",
            freq = out(reg) freq,
            options(nomem, nostack, preserves_flags),
        );
    }
    Some(freq)
}

// Agnostic

pub fn estimate_timer_frequency_hz() -> u64 {
    const DURATION: std::time::Duration = std::time::Duration::from_millis(100);

    let start_time = std::time::Instant::now();
    let start_ticks = read_ticks();
    while start_time.elapsed() < DURATION {
        std::hint::spin_loop();
    }
    let elapsed_ticks = read_ticks().wrapping_sub(start_ticks);
    (elapsed_ticks as f64 / start_time.elapsed().as_secs_f64()) as u64
}

#[cfg(test)]
mod tests {
    #[test]
    fn frequency_fallback_measures_a_nonzero_interval() {
        let start = std::time::Instant::now();
        let frequency = super::estimate_timer_frequency_hz();
        assert!(start.elapsed() >= std::time::Duration::from_millis(100));
        assert!(frequency > 0);
    }
}
