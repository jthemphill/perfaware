/// Read the ARM virtual counter directly.
/// The execution environment must allow EL0 access to the timer registers.
#[inline(always)]
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
    (freq > 0).then_some(freq)
}

pub fn timer_name() -> &'static str {
    "ARM virtual counter"
}
