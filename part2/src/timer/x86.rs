/// Read the x86 timestamp counter (TSC)
#[inline(always)]
pub fn read_ticks() -> u64 {
    unsafe { core::arch::x86_64::_rdtsc() }
}

pub fn timer_frequency_hz() -> Option<u64> {
    use core::arch::x86_64::__cpuid;
    if __cpuid(0).eax < 0x15 {
        return None;
    }
    let info = __cpuid(0x15);
    if info.eax == 0 || info.ebx == 0 || info.ecx == 0 {
        return None;
    }
    let frequency = u64::from(info.ecx) * u64::from(info.ebx) / u64::from(info.eax);
    (frequency > 0).then_some(frequency)
}

pub fn timer_name() -> &'static str {
    "x86 TSC"
}
