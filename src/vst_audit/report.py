"""Affichage console (rich). Travaille sur les dicts sérialisés : même rendu en direct ou depuis l'historique."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .diff import ScanDiff
from .grouping import PluginGroup, group_plugins
from .models import Verdict
from .store import ScanInfo
from . import insights

console = Console()

STYLE = {
    Verdict.BROKEN: ("✖", "bold white on red"),
    Verdict.KEY_REQUIRED: ("⚿", "bold black on dark_orange"),
    Verdict.NOT_OWNED: ("∅", "white on grey35"),
    Verdict.DEMO: ("◐", "bold black on yellow"),
    Verdict.DISABLED: ("⏸", "bold white on blue"),
    Verdict.TO_CHECK: ("?", "black on cyan"),
    Verdict.OK: ("✔", "bold black on green"),
}
COLOR = {
    Verdict.BROKEN: "red", Verdict.KEY_REQUIRED: "dark_orange", Verdict.NOT_OWNED: "grey50",
    Verdict.DEMO: "yellow", Verdict.DISABLED: "blue", Verdict.TO_CHECK: "cyan", Verdict.OK: "green",
}
# verdicts listés un par un dans « Points d'attention » (les autres sont résumés par éditeur)
ATTENTION = {Verdict.BROKEN, Verdict.KEY_REQUIRED, Verdict.DEMO, Verdict.DISABLED}


def badge(verdict: Verdict) -> Text:
    icon, style = STYLE[verdict]
    return Text(f" {icon} {verdict} ", style=style)


def _formats(group: PluginGroup) -> Text:
    text = Text()
    by_format: dict[str, Verdict] = {}
    for item in group.items:  # un format peut exister deux fois (VST2 mono/stéréo UAD)
        v = Verdict(item["verdict"])
        if item["format"] not in by_format or v.rank < by_format[item["format"]].rank:
            by_format[item["format"]] = v
    for fmt, v in sorted(by_format.items()):
        text.append(f"{fmt} ", style=COLOR[v] + (" strike" if v == Verdict.BROKEN else ""))
    return text


# --- Sections -----------------------------------------------------------------

def header(info: ScanInfo, title: str = "Analyse des plugins") -> None:
    hosts = ", ".join(info.hosts) or "aucune"
    console.print(Panel(
        Text.assemble(
            ("Analyse ", "dim"), (f"#{info.id}", "bold"), ("  ·  ", "dim"),
            info.started_at.replace("T", " "), ("  ·  ", "dim"), info.machine, ("  ·  ", "dim"),
            (f"{info.total} bundles", "bold"), (f" en {info.duration_s:.1f} s", "dim"),
            ("\nDAW lues : ", "dim"), hosts,
        ),
        title=f"[bold]🎛  {title}[/]", title_align="left", border_style="bright_blue", box=box.ROUNDED,
    ))


def summary(plugins: list[dict], groups: list[PluginGroup]) -> None:
    counts = Counter(g.verdict for g in groups)
    total = len(groups) or 1
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False, expand=False)
    table.add_column("Statut", no_wrap=True)
    table.add_column("Plugins", justify="right")
    table.add_column("", min_width=30)
    for verdict in Verdict:
        n = counts.get(verdict, 0)
        bar = Text("█" * round(30 * n / total) or ("▏" if n else ""), style=COLOR[verdict])
        table.add_row(badge(verdict), str(n), bar)

    formats = Counter(p["format"] for p in plugins)
    fmt_line = Text("Formats : ", style="dim")
    for fmt, n in sorted(formats.items()):
        fmt_line.append(f"{fmt} {n}   ")
    console.print(Panel(Group(table, fmt_line),
                        title=f"[bold]Synthèse[/] [dim]({len(groups)} plugins uniques, tous formats confondus)[/]",
                        title_align="left", border_style="grey50", box=box.ROUNDED))


def vendors_table(groups: list[PluginGroup], limit: int | None = 20) -> None:
    by_vendor: dict[str, list[PluginGroup]] = defaultdict(list)
    for g in groups:
        by_vendor[g.vendor].append(g)

    table = Table(title="Par éditeur", title_justify="left", title_style="bold",
                  box=box.SIMPLE_HEAVY, header_style="bold", row_styles=["", "on grey11"])
    table.add_column("Éditeur")
    for verdict in Verdict:
        icon, _ = STYLE[verdict]
        table.add_column(f"{icon}", justify="right", style=COLOR[verdict], header_style=COLOR[verdict])
    table.add_column("Total", justify="right", style="bold")

    def severity(item):
        c = Counter(g.verdict for g in item[1])
        return tuple(-c.get(v, 0) for v in Verdict)

    rows = sorted(by_vendor.items(), key=severity)
    for vendor, items in rows[:limit]:
        c = Counter(g.verdict for g in items)
        table.add_row(vendor, *[str(c[v]) if c[v] else "·" for v in Verdict], str(len(items)))
    hidden = rows[limit:] if limit else []
    if hidden:
        table.caption = (f"… {len(hidden)} autres éditeurs ({sum(len(i) for _, i in hidden)} plugins) "
                         "· --detail pour tout voir")
        table.caption_justify = "left"
    console.print(table)
    console.print(Text("   " + "   ".join(f"{STYLE[v][0]} {v}" for v in Verdict), style="dim"))
    console.print()


def plugins_table(groups: list[PluginGroup], title: str) -> None:
    if not groups:
        return
    table = Table(title=title, title_justify="left", title_style="bold", expand=True,
                  box=box.SIMPLE_HEAVY, header_style="bold", show_lines=False)
    table.add_column("Statut", no_wrap=True)
    table.add_column("Plugin", style="bold", ratio=2)
    table.add_column("Éditeur", style="dim", ratio=1)
    table.add_column("Formats", no_wrap=True)
    table.add_column("Version", style="dim", max_width=12, overflow="ellipsis", no_wrap=True)
    table.add_column("Licence", no_wrap=True)
    table.add_column("Remarques", overflow="fold", ratio=3)
    for g in groups:
        first = g.main
        lic = Text(first["license"])
        if first["license_source"]:
            lic.append(f" · {first['license_source']}", style="dim")
        notes = Text("\n".join(g.issues), style="yellow")
        if first["license_detail"]:
            if notes:
                notes.append("\n")
            notes.append(first["license_detail"], style="dim")
        versions = ", ".join(sorted({i["version"] for i in g.items if i["version"]}))
        table.add_row(badge(g.verdict), g.name, g.vendor, _formats(g), versions, lic, notes)
    console.print(table)


TIP_STYLE = {"clé": "dark_orange", "uad": "cyan", "non_acquis": "grey50", "invalide": "red", "nettoyage": "red"}


def actions(groups: list[PluginGroup]) -> None:
    lines = [Text.assemble((f"{t.icon} ", TIP_STYLE[t.kind]), (t.title, "bold"), f" {t.text}")
             for t in insights.todo(groups)]
    if lines:
        console.print(Panel(Group(*lines), title="[bold]À faire[/]", title_align="left",
                            border_style="dark_orange", box=box.ROUNDED))


def diff_section(diff: ScanDiff, old_id: int, new_id: int, limit: int = 30) -> None:
    title = f"[bold]Évolution[/] [dim]#{old_id} → #{new_id}[/]"
    if diff.empty:
        console.print(Panel(Text("Aucun changement depuis l'analyse précédente.", style="green"),
                            title=title, title_align="left", border_style="grey50", box=box.ROUNDED))
        return

    parts = []
    if diff.transitions:
        moves = Table(box=None, show_header=False, pad_edge=False)
        for (before, after), n in diff.transitions.most_common():
            moves.add_row(badge(Verdict(before)), "→", badge(Verdict(after)), Text(f"{n} plugin(s)", style="bold"))
        parts += [Text("Changements de statut", style="bold underline"), moves, Text()]

    table = Table(box=box.SIMPLE, header_style="bold", pad_edge=False)
    table.add_column("", no_wrap=True)
    table.add_column("Plugin", style="bold")
    table.add_column("Éditeur", style="dim")
    table.add_column("Changement")
    rows = ([(Text("+ ajouté", style="green"), g, badge(g.verdict)) for g in diff.added]
            + [(Text("− retiré", style="red"), g, Text(_formats(g).plain, style="dim")) for g in diff.removed])
    for c in diff.changed:
        if c.what == "statut":
            change = Text.assemble(badge(Verdict(c.before)), " → ", badge(Verdict(c.after)))
        else:
            change = Text.assemble((c.what, "dim"), " : ", (c.before or "∅", "red"), " → ", (c.after or "∅", "green"))
        rows.append((Text("~ modifié", style="yellow"), c.group, change))
    for tag, g, change in rows[:limit]:
        table.add_row(tag, g.name, g.vendor, change)
    parts.append(table)
    if len(rows) > limit:
        parts.append(Text(f"… et {len(rows) - limit} autres lignes (vst-audit comparer --limite 0 pour tout voir)",
                          style="dim"))

    console.print(Panel(Group(*parts), title=title, title_align="left", border_style="yellow", box=box.ROUNDED,
                        subtitle=f"[green]+{len(diff.added)}[/] [red]−{len(diff.removed)}[/] "
                                 f"[yellow]~{len(diff.changed)}[/]", subtitle_align="right"))


def full_report(info: ScanInfo, plugins: list[dict], detail: bool = False,
                vendor: str | None = None, status: str | None = None) -> None:
    groups = group_plugins(plugins)
    if vendor:
        groups = [g for g in groups if vendor.lower() in g.vendor.lower()]
        plugins = [p for p in plugins if vendor.lower() in p["vendor"].lower()]
    if status:
        groups = [g for g in groups if str(g.verdict) == status]

    header(info)
    summary(plugins, groups)
    vendors_table(groups, limit=None if detail or vendor else 20)
    if detail or vendor or status:
        plugins_table(groups, "Détail des plugins")
    else:
        plugins_table([g for g in groups if g.verdict in ATTENTION or g.broken_formats],
                      "Points d'attention  [dim](--detail pour tout voir)[/]")
    actions(groups)


def uad_report(plugins: list[dict], uadx_logs: int, profile_info: str | None) -> None:
    """Vue dédiée Universal Audio : sources trouvées, état par plugin, ce qu'il reste à faire."""
    groups = [g for g in group_plugins(plugins) if "uad_famille" in g.main["extra"]]
    sources = Text.assemble(
        ("Journaux UADx : ", "bold"), f"{uadx_logs} plugins avec un état de licence\n",
        ("Profil UAD-2  : ", "bold"),
        profile_info or Text("inexploitable (généré sans Apollo branché)", style="yellow"),
    )
    console.print(Panel(sources, title="[bold]🎛  Universal Audio · sources de licence[/]",
                        title_align="left", border_style="bright_blue", box=box.ROUNDED))

    for family in ("UADx natif", "UAD-2 DSP"):
        fam = [g for g in groups if g.main["extra"]["uad_famille"] == family]
        if not fam:
            continue
        by_label: dict[str, list[PluginGroup]] = defaultdict(list)
        for g in fam:
            item = next((i for i in g.items if i["license_source"].startswith("UA ")), g.main)
            label = item["license_detail"].split(" · ")[0] if item["license_source"].startswith("UA ") \
                else "aucune information"
            label = re.sub(r" (le|jusqu'au) .*$", "", label)  # regrouper les démos quelle que soit la date
            by_label[label].append(g)

        table = Table(title=f"{family} ({len(fam)} plugins)", title_justify="left", title_style="bold",
                      box=box.SIMPLE_HEAVY, header_style="bold", expand=True)
        table.add_column("Statut", no_wrap=True)
        table.add_column("Nb", justify="right")
        table.add_column("Plugins", ratio=1)
        for label, items in sorted(by_label.items(), key=lambda kv: (kv[1][0].verdict.rank, kv[0])):
            names = ", ".join(sorted(g.name.removeprefix("UADx ").removeprefix("UAD ") for g in items))
            if label == "aucune information" and len(items) > 40:
                names = names[:400] + " …"
            table.add_row(badge(items[0].verdict) if label != "aucune information" else badge(Verdict.TO_CHECK),
                          Text(f"{len(items)}", style="bold"), Text.assemble((label, "bold"), "\n", (names, "dim")))
        console.print(table)

    tips = [
        Text.assemble(("UADx sans information : ", "bold"),
                      "ouvrez chaque plugin une fois en natif dans une DAW, puis relancez l'analyse ; "
                      "son état (acheté, Spark, démo) sera lu dans son journal."),
        Text.assemble(("UAD-2 : ", "bold"), "Apollo branché, ouvrez « UAD Meter & Control Panel » → ",
                      ("System Info", "bold"), " → onglet Plug-ins, puis relancez vst-audit uad."),
        Text.assemble(("Sinon : ", "bold"), "listez vos achats dans config/licences.toml [uad].possedes "
                      "puis strict = true pour classer le reste « non acquis »."),
    ]
    console.print(Panel(Group(*tips), title="[bold]Compléter[/]", title_align="left",
                        border_style="dark_orange", box=box.ROUNDED))
