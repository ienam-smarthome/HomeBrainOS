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
