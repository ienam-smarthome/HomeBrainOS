/*
 * Independent Hubitat user app — source-only, not automatically installed.
 * TV smart plug 4221; Google TV Internet control 6923.
 * Counts cumulative plug ON time. It does not measure actual viewing minutes.
 * An Internet switch off-to-on transition begins a new allowance regardless
 * of actor; Hubitat switch events alone cannot prove manual restoration.
 */
definition(
    name: "Google TV — Cumulative Internet Allowance",
    namespace: "ienam",
    author: "HomeBrainOS",
    description: "Independent cumulative TV-on allowance and Internet block",
    category: "Convenience",
    singleInstance: false
)
preferences {
    page(name: "mainPage", title: "Google TV — Cumulative Internet Allowance")
}

def mainPage() {
    dynamicPage(name: "mainPage", title: "Google TV cumulative allowance", install: true, uninstall: true) {
        section("Exact devices") {
            input "tvPlug", "capability.switch", title: "TV metering plug — ID 4221", required: true
            input "internetControl", "capability.switch", title: "Google TV Internet control — ID 6923", required: true
            paragraph "Incorrect device IDs are rejected; the app never turns ON either device."
        }
        section("Configuration") {
            input "allowanceMinutes", "number", title: "Cumulative ON minutes",
                defaultValue: 60, required: true, range: "1..1440"
            input "enableController", "bool", title: "Enable blocking (off by default)",
                defaultValue: false, required: true
            paragraph "An observed Internet-control off → on transition resets the allowance. " +
                "The switch attribute does not identify who unblocked it. " +
                "Existing rule 3985 is not changed and could independently block the same target."
        }
        section("Status and manual counter reset") {
            paragraph statusText()
            input name: "resetCounter", type: "button",
                title: "Reset counter ONLY (never unblock Internet)"
        }
    }
}

def installed() {
    atomicState.initialized = false
    initialize()
}

def updated() {
    checkpoint(now())
    unsubscribe()
    unschedule()
    initialize()
}

def uninstalled() {
    unsubscribe()
    unschedule()
}

private boolean validDevices() {
    return tvPlug != null && internetControl != null &&
        tvPlug.id.toString() == "4221" &&
        internetControl.id.toString() == "6923" &&
        tvPlug.id.toString() != internetControl.id.toString()
}

private boolean enforcementEnabled() {
    return settings.enableController == true && validDevices()
}

private long budgetMs() {
    long minutes = 60L
    try {
        if (settings.allowanceMinutes != null)
            minutes = Long.parseLong(settings.allowanceMinutes.toString())
    } catch (Exception ignored) { minutes = 60L }
    return Math.max(1L, Math.min(1440L, minutes)) * 60000L
}

private Long parsedLong(Object input) {
    if (input == null) return null
    try { return Long.parseLong(input.toString()) }
    catch (Exception ignored) { return null }
}

private long usedMs() {
    Long value = parsedLong(atomicState.usedMs)
    return Math.max(0L, value == null ? 0L : value)
}

private String currentSwitch(def device) {
    try { return (device?.currentValue("switch") ?: "").toString().toLowerCase() }
    catch (Exception ignored) { return "" }
}

private boolean countingAllowed() {
    return enforcementEnabled() &&
        atomicState.awaitingUnblock != true &&
        atomicState.internetState == "on" &&
        atomicState.tvState == "on"
}
