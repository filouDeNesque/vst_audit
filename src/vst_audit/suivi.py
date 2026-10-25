"""Suivi interactif : ouvrir les plugins UADx un par un et noter leur état de licence.

Les résultats sont gardés dans data/uad_suivi.json. Ils servent de source au détecteur UAD
(après les journaux, qui restent prioritaires) et permettent de reprendre plus tard.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .config import DATA_DIR
from .licenses import ua_sources
from .models import License, Verdict
from .report import badge, console

SUIVI_FILE = DATA_DIR / "uad_suivi.json"

# touche -> (statut, libellé enregistré)
MANUAL = {
    "a": (License.LICENSED, "acheté (noté)"),
    "s": (License.LICENSED, "Spark (noté)"),
    "d": (License.DEMO, "démo (notée)"),
    "n": (License.NOT_OWNED, "non acquis (noté)"),
}
VERDICT_OF = {License.LICENSED: Verdict.OK, License.DEMO: Verdict.DEMO, License.NOT_OWNED: Verdict.NOT_OWNED}


@dataclass
class Item:
    plugin_id: str  # « uaudio_ua_1176 », comme dans les journaux
    name: str       # nom affiché dans la DAW (AU)
    formats: str


def build_items(plugins: list, include_known: bool = False) -> list[Item]:
    """UADx à suivre : un élément par identifiant de plugin, sans état connu par journal (sauf include_known)."""
    from .licenses import uad

    known = ua_sources.uadx_states()
    by_id: dict[str, list] = {}
    for p in plugins:
        if uad.is_uad(p) and uad.family(p) == "UADx natif":
            by_id.setdefault(uad.plugin_id(p), []).append(p)
    items = []
    for pid, group in by_id.items():
        if pid in known and not include_known:
            continue
        main = next((p for p in group if p.format == "AU"), group[0])  # nom vu dans les DAW
        items.append(Item(pid, main.name, " ".join(sorted({str(p.format) for p in group}))))
    return sorted(items, key=lambda i: i.name.lower())


def load(path: Path | None = None) -> dict[str, dict]:
    path = path or SUIVI_FILE
    try:
        return json.loads(path.read_text()).get("plugins", {})
    except (OSError, ValueError):
        return {}


@cache
def notes() -> dict[str, dict]:
    """Version mise en cache pour le détecteur (une lecture par analyse)."""
    return load()


def save(entries: dict[str, dict], path: Path | None = None) -> None:
    path = path or SUIVI_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "plugins": entries}, ensure_ascii=False, indent=2))
    tmp.replace(path)  # écriture atomique : rien de perdu si on quitte brutalement


def record(entries: dict, item: Item, status: License, label: str, source: str, note: str = "") -> None:
    entries[item.plugin_id] = {
        "name": item.name, "status": status.value, "label": label, "source": source,
        "note": note, "date": datetime.now().isoformat(timespec="seconds"),
    }
    save(entries)


def _status_text(entry: dict | None) -> Text:
    if not entry:
        return Text("○ à faire", style="dim")
    return Text.assemble(badge(VERDICT_OF[License(entry["status"])]), " ", (entry["label"], "dim"))


def overview(items: list[Item], entries: dict) -> None:
    done = sum(1 for i in items if i.plugin_id in entries)
    table = Table(box=box.SIMPLE, header_style="bold", pad_edge=False, expand=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Plugin", style="bold")
    table.add_column("État")
    table.add_column("Note", style="italic dim")
    for n, item in enumerate(items, 1):
        entry = entries.get(item.plugin_id)
        table.add_row(str(n), item.name, _status_text(entry), (entry or {}).get("note", ""))
    console.print(Panel(table, title=f"[bold]Suivi UADx[/] [dim]{done}/{len(items)} traités[/]",
                        title_align="left", border_style="bright_blue", box=box.ROUNDED))


def _progress(done: int, total: int) -> Table:
    grid = Table.grid(padding=(0, 1))
    grid.add_row(ProgressBar(total=total, completed=done, width=40), Text(f"{done}/{total}", style="bold"))
    return grid


HELP = Text.assemble(
    ("Entrée", "bold cyan"), " vérifier le journal   ",
    ("a", "bold green"), " acheté   ", ("s", "bold green"), " Spark   ",
    ("d", "bold yellow"), " démo   ", ("n", "bold"), " non acquis   ",
    ("p", "bold"), " passer   ", ("q", "bold red"), " quitter",
)


def run(items: list[Item], redo: bool = False) -> None:
    entries = load()
    todo = [i for i in items if redo or i.plugin_id not in entries]
    overview(items, entries)
    if not todo:
        console.print("[green]Tout est traité.[/] Relancez avec [bold]--refaire[/] pour tout revérifier.")
        return

    console.print(Panel(Text.assemble(
        "Pour chaque plugin : ouvrez-le dans une DAW (Logic, Live…), puis revenez ici et appuyez sur ",
        ("Entrée", "bold"), ".\nL'état est lu dans le journal que le plugin vient d'écrire. Si rien n'apparaît, "
        "notez ce que vous voyez dans le plugin (bandeau « Try / Buy », Spark…).\n",
        ("Astuce : ", "bold"), "le journal de licence n'est écrit qu'en mode natif. Avec l'Apollo branché, "
        "le plugin peut tourner sur le DSP sans vérifier de licence : passez-le en mode natif ou débranchez l'Apollo.",
    ), title="[bold]Mode d'emploi[/]", title_align="left", border_style="grey50", box=box.ROUNDED))

    for item in todo:
        done = sum(1 for i in items if i.plugin_id in entries)
        console.rule(style="grey35")
        console.print(_progress(done, len(items)))
        console.print(Panel(Text.assemble(
            ("Dans la DAW, cherchez : ", "dim"), (item.name, "bold"),
            ("\nFormats installés : ", "dim"), item.formats,
            ("\nÉtat actuel : ", "dim"), _status_text(entries.get(item.plugin_id)),
        ), title=f"[bold]{item.name}[/]", title_align="left", border_style="cyan", box=box.ROUNDED))
        console.print(HELP)

        while True:
            choice = Prompt.ask("→", choices=["", *MANUAL, "p", "q"], default="", show_choices=False,
                                show_default=False, console=console).strip().lower()
            if choice == "q":
                save(entries)
                console.print("[dim]Progression enregistrée. Reprenez avec[/] [bold]vst-audit uad --suivi[/].")
                overview(items, entries)
                return
            if choice == "p":
                console.print("[dim]Passé.[/]")
                break
            if choice in MANUAL:
                status, label = MANUAL[choice]
                note = Prompt.ask("Note (facultatif)", default="", show_default=False, console=console)
                record(entries, item, status, label, "manuel", note)
                console.print(Text.assemble("✔ noté : ", badge(VERDICT_OF[status]), f" {label}"))
                break
            state = ua_sources.read_uadx_states(only=item.plugin_id).get(item.plugin_id)
            if not state:
                console.print("[yellow]Aucun état de licence dans le journal.[/] Le plugin a-t-il été ouvert "
                              "en mode natif ? Réessayez avec Entrée, ou notez-le à la main (a / s / d / n).")
                continue
            console.print(Text.assemble("Journal : ", badge(VERDICT_OF.get(state.status, Verdict.TO_CHECK)),
                                        f" {state.label} ", (f"({state.seen:%d/%m/%Y %H:%M})", "dim")))
            if Confirm.ask("Valider ?", default=True, console=console):
                note = Prompt.ask("Note (facultatif)", default="", show_default=False, console=console)
                record(entries, item, state.status, state.label, "journal", note)
                break

    console.rule(style="grey35")
    overview(items, entries)
    console.print("[green]Terminé.[/] Ces résultats sont pris en compte par [bold]vst-audit scan[/].")
