"""Point d'entrée : `vst-audit scan | uad | web | historique | voir | comparer`."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.logging import RichHandler
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import config, pipeline, report, store
from .diff import compare
from .models import Verdict
from .report import console

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Analyse des plugins audio : validité, licences, démos, historique.")
log = logging.getLogger("vst_audit")

LOG_DIR = config.DATA_DIR / "logs"


def setup_logging(verbose: int, started: datetime | None = None) -> Path | None:
    level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    console_handler = RichHandler(console=console, show_path=False, markup=False, rich_tracebacks=True)
    console_handler.setLevel(level)
    handlers: list[logging.Handler] = [console_handler]
    log_file = None
    if started:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{started:%Y-%m-%d_%H%M%S}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s : %(message)s"))
        handlers.append(file_handler)
    logging.basicConfig(level=logging.DEBUG, handlers=handlers, format="%(message)s", force=True)
    return log_file


Verbose = Annotated[int, typer.Option("--verbose", "-v", count=True, help="-v infos, -vv débogage")]
VendorOpt = Annotated[Optional[str], typer.Option("--editeur", "-e", help="Filtrer sur un éditeur")]
StatusOpt = Annotated[Optional[str], typer.Option("--statut", "-s", help=f"Filtrer : {', '.join(Verdict)}")]
DetailOpt = Annotated[bool, typer.Option("--detail", "-d", help="Lister tous les plugins")]


def _check_status(status: str | None) -> None:
    if status and status not in {v.value for v in Verdict}:
        raise typer.BadParameter(f"statut inconnu « {status} » ({', '.join(Verdict)})")


@app.command()
def scan(
    detail: DetailOpt = False,
    vendor: VendorOpt = None,
    status: StatusOpt = None,
    signatures: Annotated[bool, typer.Option("--signatures", help="Vérifier les signatures (codesign, plus lent)")] = False,
    no_save: Annotated[bool, typer.Option("--no-save", help="Ne pas enregistrer dans l'historique")] = False,
    verbose: Verbose = 0,
) -> None:
    """Analyse les plugins installés et enregistre le résultat."""
    _check_status(status)
    started = datetime.now()
    log_file = setup_logging(verbose, None if no_save else started)

    with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
                  MofNCompleteColumn(), TimeElapsedColumn(), console=console, transient=True) as progress:
        tasks: dict[str, int] = {}

        def on_step(name: str, done: int, total: int) -> None:
            if name not in tasks:
                tasks[name] = progress.add_task(name, total=total or None)
            progress.update(tasks[name], completed=done)

        result = pipeline.run_scan(signatures=signatures, on_step=on_step)
    plugins, found_hosts, duration = result.plugins, result.hosts, result.duration
    data = [p.to_dict() for p in plugins]
    if no_save:
        info = store.ScanInfo(0, started.isoformat(timespec="seconds"), "—", duration, len(plugins), found_hosts)
    else:
        info = store.save(plugins, started, duration, found_hosts)

    report.full_report(info, data, detail=detail, vendor=vendor, status=status)

    if not no_save:
        prev = store.previous_id(info.id)
        if prev:
            old = store.load_scan(prev)
            report.diff_section(compare(old[1], data), prev, info.id)
        console.print(f"[dim]Analyse #{info.id} enregistrée · journal : {log_file}[/]")


@app.command("uad")
def uad_cmd(
    suivi_mode: Annotated[bool, typer.Option("--suivi", help="Ouvrir les UADx un par un et noter leur état")] = False,
    redo: Annotated[bool, typer.Option("--refaire", help="Avec --suivi : repasser aussi les plugins déjà traités")] = False,
    tous: Annotated[bool, typer.Option("--tous", help="Avec --suivi : inclure les UADx déjà connus par leur journal")] = False,
    verbose: Verbose = 0,
) -> None:
    """Licences Universal Audio : achats, Spark, démos, d'après les fichiers locaux d'UA."""
    from . import suivi
    from .licenses import ua_sources

    setup_logging(verbose)
    plugins = pipeline.run_scan().plugins

    if suivi_mode:
        suivi.run(suivi.build_items(plugins, include_known=tous), redo=redo)
        return

    profile = ua_sources.system_profile()
    profile_info = f"{len(profile.products)} produits, profil du {profile.date}" if profile else None
    report.uad_report([p.to_dict() for p in plugins], len(ua_sources.uadx_states()), profile_info)


@app.command("sonder")
def probe_cmd(
    vendor: VendorOpt = None,
    status: Annotated[Optional[str], typer.Option("--statut", "-s", help="Statut à sonder (défaut : à vérifier)")] = "à vérifier",
    name: Annotated[Optional[str], typer.Option("--plugin", "-p", help="Nom (ou partie du nom) d'un plugin")] = None,
    limit: Annotated[int, typer.Option("--limite", "-n", help="Nombre maximum de plugins")] = 0,
    no_gui: Annotated[bool, typer.Option("--sans-interface", help="Ne pas ouvrir l'interface (son seulement)")] = False,
    redo: Annotated[bool, typer.Option("--refaire", help="Resonder même les plugins déjà sondés avec succès")] = False,
    yes: Annotated[bool, typer.Option("--oui", "-y", help="Ne pas demander de confirmation")] = False,
    verbose: Verbose = 0,
) -> None:
    """Vérification active : charge chaque plugin, écoute ce qu'il produit et lit son interface."""
    from rich.table import Table as RichTable

    from . import sonde
    from .grouping import group_plugins
    from .report import badge

    _check_status(status if status != "tous" else None)
    setup_logging(verbose)
    if solved := sonde.reclassify_stored():
        console.print(f"[green]{solved} ancien(s) résultat(s) reclassé(s)[/] avec la logique actuelle, sans resonder")
    result = pipeline.run_scan()
    groups = group_plugins([p.to_dict() for p in result.plugins])
    done = sonde.load()
    todo = [g for g in groups
            if (not vendor or vendor.lower() in g.vendor.lower())
            and (not name or name.lower() in g.name.lower())
            and (name or status in (None, "tous") or g.verdict.value == status)
            and (redo or sonde.needs_probe(done.get(g.key)))]
    # les plugins non sondables (Intel, plugins-hôtes) sont seulement notés, sans être chargés
    todo = [g for g in todo if not sonde.unprobeable(g.items)] + [g for g in todo if sonde.unprobeable(g.items)]
    if limit:
        todo = todo[:limit]
    if not todo:
        console.print("[green]Rien à sonder.[/] (--refaire pour resonder, --statut tous pour élargir)")
        return

    per = 10 if no_gui else 25
    loadable = sum(1 for g in todo if not sonde.unprobeable(g.items))
    console.print(f"[bold]{len(todo)} plugin(s)[/] dont {loadable} à charger · environ {loadable * per // 60 + 1} min"
                  + ("" if no_gui or not loadable else " · [yellow]leurs fenêtres vont s'ouvrir quelques secondes à l'écran[/]"))
    if loadable > 5 and not yes and not typer.confirm("Continuer ?", default=True):
        raise typer.Exit()

    rows = []
    with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(), MofNCompleteColumn(),
                  TimeElapsedColumn(), console=console, transient=True) as progress:
        task = progress.add_task("Sonde", total=len(todo))
        failures: dict[str, int] = {}  # échecs consécutifs (plantage / blocage) par éditeur
        preferred: dict[str, str] = {}  # format qui a fonctionné après un repli, par éditeur
        for g in todo:
            if failures.get(g.vendor, 0) >= 3:
                console.print(f"[dim]↷ {g.name} : ignoré, 3 échecs de suite chez {g.vendor} (relancez avec -e pour réessayer)[/]")
                progress.advance(task)
                continue
            progress.update(task, description=f"Sonde · {g.name[:40]}")
            entry = sonde.probe_group(g.key, g.name, g.vendor, g.items, gui=not no_gui, prefer=preferred.get(g.vendor))
            raw = entry["raw"]
            if any(e.startswith("essais ratés") for e in entry["evidence"]) and not (raw.get("crash") or raw.get("timeout")):
                preferred[g.vendor] = entry["format"]  # le repli a marché : on commence par ce format
            failures[g.vendor] = failures.get(g.vendor, 0) + 1 if (raw.get("crash") or raw.get("timeout")) else 0
            rows.append((g, entry))
            verdict = {"licencié": Verdict.OK, "clé requise": Verdict.KEY_REQUIRED, "démo": Verdict.DEMO,
                       "non acquis": Verdict.NOT_OWNED}.get(entry["status"] or "", Verdict.TO_CHECK)
            console.print(badge(verdict), f"[bold]{g.name}[/] [dim]{g.vendor} · {entry['format'] or '—'}[/] — {entry['label']}")
            progress.advance(task)

    table = RichTable(title="Résultats de la sonde", title_justify="left", title_style="bold")
    table.add_column("Résultat")
    table.add_column("Plugins", justify="right")
    from collections import Counter
    for label, n in Counter(e["status"] or "non concluant" for _, e in rows).most_common():
        table.add_row(label, str(n))
    console.print(table)
    console.print("[dim]Résultats pris en compte par scan et par l'interface web · détails : data/sondes.json[/]")


@app.command("historique")
def history(limit: Annotated[int, typer.Option("--limite", "-n")] = 20) -> None:
    """Liste les analyses enregistrées."""
    setup_logging(0)
    scans = store.list_scans(limit)
    if not scans:
        console.print("[yellow]Aucune analyse enregistrée. Lancez [bold]vst-audit scan[/].[/]")
        return
    table = Table(title="Historique des analyses", title_justify="left", title_style="bold")
    for col in ("#", "Date", "Machine", "Bundles", "Durée", "DAW"):
        table.add_column(col, justify="right" if col in ("#", "Bundles", "Durée") else "left", no_wrap=True)
    for s in scans:
        table.add_row(str(s.id), s.started_at.replace("T", " "), s.machine, str(s.total),
                      f"{s.duration_s:.1f} s", ", ".join(s.hosts))
    console.print(table)


@app.command("voir")
def show(
    scan_id: Annotated[Optional[int], typer.Argument(help="Numéro d'analyse (défaut : la dernière)")] = None,
    detail: DetailOpt = False,
    vendor: VendorOpt = None,
    status: StatusOpt = None,
) -> None:
    """Réaffiche une analyse enregistrée, sans rescanner."""
    _check_status(status)
    setup_logging(0)
    loaded = store.load_scan(scan_id)
    if not loaded:
        console.print("[red]Analyse introuvable.[/]")
        raise typer.Exit(1)
    report.full_report(*loaded, detail=detail, vendor=vendor, status=status)


@app.command("comparer")
def diff_cmd(
    old_id: Annotated[Optional[int], typer.Argument(help="Analyse de référence (défaut : avant-dernière)")] = None,
    new_id: Annotated[Optional[int], typer.Argument(help="Analyse à comparer (défaut : dernière)")] = None,
    limit: Annotated[int, typer.Option("--limite", "-n", help="Lignes affichées (0 = toutes)")] = 50,
) -> None:
    """Compare deux analyses : ajouts, retraits, changements de statut ou de version."""
    setup_logging(0)
    new = store.load_scan(new_id)
    if not new:
        console.print("[red]Analyse introuvable.[/]")
        raise typer.Exit(1)
    old_id = old_id or store.previous_id(new[0].id)
    old = store.load_scan(old_id) if old_id else None
    if not old:
        console.print("[yellow]Il faut au moins deux analyses pour comparer.[/]")
        raise typer.Exit(1)
    report.diff_section(compare(old[1], new[1]), old[0].id, new[0].id, limit=limit or 10**9)


@app.command("web")
def web(
    port: Annotated[int, typer.Option("--port", "-p")] = 8765,
    open_browser: Annotated[bool, typer.Option("--ouvrir/--pas-ouvrir", help="Ouvrir le navigateur")] = True,
    verbose: Verbose = 0,
) -> None:
    """Interface web locale (http://127.0.0.1:8765) et son API (/api/docs)."""
    import threading
    import webbrowser

    import uvicorn

    setup_logging(verbose)
    url = f"http://127.0.0.1:{port}"
    console.print(f"[bold]🎛  vst-audit[/] → [link={url}]{url}[/]  ·  API : {url}/api/docs  ·  Ctrl+C pour arrêter")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    # 127.0.0.1 uniquement : l'API peut lancer des commandes locales (Finder, codesign, auval)
    uvicorn.run("vst_audit.api:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    app()
