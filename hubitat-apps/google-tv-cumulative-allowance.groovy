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

def initialize() {
    unsubscribe()
    unschedule()
    atomicState.activeSinceMs = null
    if (!validDevices()) {
        log.warn "TV allowance disabled: select exact IDs 4221 and 6923."
        return
    }
    String tvNow = currentSwitch(tvPlug)
    String internetNow = currentSwitch(internetControl)
    String previousInternet = (atomicState.internetState ?: "").toString()
    if (atomicState.initialized != true) {
        atomicState.usedMs = 0L
        atomicState.awaitingUnblock = internetNow != "on"
        atomicState.blockPending = false
        atomicState.blockAttempts = 0
        atomicState.lastResetMs = now()
        atomicState.initialized = true
    } else if (previousInternet == "off" && internetNow == "on") {
        // A transition may have occurred while Hubitat was restarting.
        resetAllowance(now(), "access restored across restart")
    } else if (internetNow != "on") {
        atomicState.awaitingUnblock = true
    }
    atomicState.tvState = tvNow
    atomicState.internetState = internetNow
    subscribe(tvPlug, "switch", tvSwitchChanged)
    subscribe(internetControl, "switch", internetSwitchChanged)
    if (!enforcementEnabled()) {
        log.info "Allowance installed but DISABLED; no Internet control commands."
        return
    }
    if (countingAllowed()) atomicState.activeSinceMs = now()
    evaluate(now())
}

private void checkpoint(long timestamp) {
    Long started = parsedLong(atomicState.activeSinceMs)
    if (started == null) return
    long elapsed = Math.max(0L, timestamp - started)
    // Do not charge hours while Hubitat is offline or its clock jumps.
    // The 60-second checkpoints bound normal reboot loss to about one minute.
    if (elapsed > 120000L) {
        log.warn "Unverified clock gap; only 120 seconds may be credited."
        elapsed = 120000L
    }
    atomicState.usedMs = Math.min(budgetMs(), usedMs() + elapsed)
    atomicState.activeSinceMs = timestamp
}

private void stopCounting() {
    atomicState.activeSinceMs = null
    unschedule("usageTick")
}

private void resetAllowance(long timestamp, String reason) {
    atomicState.usedMs = 0L
    atomicState.lastResetMs = timestamp
    atomicState.awaitingUnblock = false
    atomicState.blockPending = false
    atomicState.blockAttempts = 0
    atomicState.activeSinceMs = null
    atomicState.lastError = null
    unschedule("verifyBlock")
    unschedule("awaitUnblockPoll")
    log.info "New TV allowance: " + reason
}

def tvSwitchChanged(evt) {
    if (!validDevices()) return
    long timestamp = now()
    checkpoint(timestamp)  // settle prior ON span before processing new state
    String nextState = (evt?.value ?: "").toString().toLowerCase()
    if (nextState != "on" && nextState != "off") return
    atomicState.tvState = nextState
    stopCounting()
    evaluate(timestamp)
}

def internetSwitchChanged(evt) {
    if (!validDevices()) return
    long timestamp = now()
    checkpoint(timestamp)
    String previous = (atomicState.internetState ?: "").toString()
    String incoming = (evt?.value ?: "").toString().toLowerCase()
    if (incoming != "on" && incoming != "off") return
    atomicState.internetState = incoming
    stopCounting()
    if (previous == "off" && incoming == "on") {
        // The event proves a state change, NOT whether a person caused it.
        resetAllowance(timestamp, "Internet off to on")
    } else if (incoming == "off") {
        atomicState.awaitingUnblock = true
        atomicState.blockPending = false
        atomicState.lastBlockedMs = timestamp
        unschedule("verifyBlock")
    }
    evaluate(timestamp)
}
