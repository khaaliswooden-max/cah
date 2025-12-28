"""
Main CLI Entry Point

Command-line interface for CAH Transformation Engine operations.
"""

import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from cah_engine import __version__
from cah_engine.storage.database import get_database, close_database
from cah_engine.storage.repositories import (
    EncounterRepository,
    MetricsRepository,
    ComplianceRepository,
    CostReportRepository,
)


console = Console()


def print_banner():
    """Print application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║           CAH Transformation Engine v{version}               ║
║     Critical Access Hospital Decision Support System          ║
╚═══════════════════════════════════════════════════════════════╝
    """.format(version=__version__)
    console.print(banner, style="bold blue")


@click.group()
@click.version_option(version=__version__)
@click.option('--db-path', type=click.Path(), help='Database path')
@click.pass_context
def cli(ctx, db_path):
    """CAH Transformation Engine - Decision support for Critical Access Hospitals."""
    ctx.ensure_object(dict)
    
    if db_path:
        ctx.obj['db_path'] = Path(db_path)
    else:
        ctx.obj['db_path'] = Path.home() / ".cah" / "cah_data.db"


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize the CAH database and configuration."""
    print_banner()
    
    db_path = ctx.obj['db_path']
    console.print(f"\n[bold]Initializing database at:[/bold] {db_path}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating database...", total=None)
        
        try:
            db = get_database(db_path)
            progress.update(task, description="Database initialized successfully")
            
            stats = db.get_stats()
            console.print(f"\n[green]✓[/green] Database ready")
            console.print(f"  Path: {stats['path']}")
            console.print(f"  Size: {stats['size_mb']:.2f} MB")
            
        except Exception as e:
            console.print(f"\n[red]✗[/red] Error: {e}")
            sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status and data freshness."""
    print_banner()
    
    db = get_database(ctx.obj['db_path'])
    
    # Database stats
    stats = db.get_stats()
    
    table = Table(title="System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")
    
    table.add_row(
        "Database",
        "Online",
        f"{stats['size_mb']:.2f} MB"
    )
    table.add_row(
        "Encounters",
        str(stats.get('encounters_count', 0)),
        "records"
    )
    table.add_row(
        "Cost Reports",
        str(stats.get('cost_reports_count', 0)),
        "records"
    )
    table.add_row(
        "Metrics",
        str(stats.get('metrics_history_count', 0)),
        "data points"
    )
    
    console.print(table)
    
    # Sync status
    from cah_engine.storage.offline import OfflineManager
    offline_mgr = OfflineManager(db)
    sync_status = offline_mgr.get_sync_status()
    
    console.print(f"\n[bold]Sync Status:[/bold] {sync_status['status']}")
    if sync_status['last_sync']:
        console.print(f"  Last sync: {sync_status['last_sync']}")
    if sync_status['pending_items'] > 0:
        console.print(f"  [yellow]Pending items: {sync_status['pending_items']}[/yellow]")


@cli.group()
def data():
    """Data import and export commands."""
    pass


@data.command('import-ehr')
@click.argument('source', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['ccda', 'hl7', 'csv']), help='Source format')
@click.pass_context
def import_ehr(ctx, source, format):
    """Import EHR data from file or directory."""
    from cah_engine.foundation.ehr_extract import EHRExtractor
    
    console.print(f"\n[bold]Importing EHR data from:[/bold] {source}")
    
    extractor = EHRExtractor()
    source_path = Path(source)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting encounters...", total=None)
        
        if source_path.is_dir():
            result = extractor.extract_directory(source_path)
        else:
            result = extractor.extract(source_path)
        
        progress.update(task, description=f"Extracted {len(result.encounters)} encounters")
    
    # Save to database
    db = get_database(ctx.obj['db_path'])
    repo = EncounterRepository(db)
    
    count = repo.save_batch(result.encounters)
    
    console.print(f"\n[green]✓[/green] Imported {count} encounters")
    
    if result.errors:
        console.print(f"[yellow]Warnings: {len(result.errors)}[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


@data.command('import-cost-report')
@click.argument('source', type=click.Path(exists=True))
@click.pass_context
def import_cost_report(ctx, source):
    """Import cost report data."""
    from cah_engine.foundation.cost_report import CostReportParser
    
    console.print(f"\n[bold]Importing cost report from:[/bold] {source}")
    
    parser = CostReportParser()
    result = parser.parse(source)
    
    if result.metrics:
        db = get_database(ctx.obj['db_path'])
        repo = CostReportRepository(db)
        repo.save(result.metrics)
        
        console.print(f"\n[green]✓[/green] Imported cost report for {result.metrics.provider_id}")
        console.print(f"  Fiscal year: {result.metrics.fiscal_year_end}")
        console.print(f"  Staffed beds: {result.metrics.staffed_beds}")
        console.print(f"  Operating margin: {result.metrics.operating_margin:.1f}%")
    else:
        console.print(f"\n[red]✗[/red] Failed to parse cost report")
        for error in result.errors:
            console.print(f"  - {error}")


@data.command('export')
@click.argument('output', type=click.Path())
@click.option('--format', type=click.Choice(['json', 'csv', 'fhir']), default='json')
@click.option('--type', 'data_type', type=click.Choice(['encounters', 'metrics', 'all']), default='all')
@click.pass_context
def export_data(ctx, output, format, data_type):
    """Export data to file."""
    db = get_database(ctx.obj['db_path'])
    
    console.print(f"\n[bold]Exporting {data_type} to:[/bold] {output}")
    
    data = {}
    
    if data_type in ('encounters', 'all'):
        repo = EncounterRepository(db)
        encounters = repo.get_recent(days=365)
        data['encounters'] = [e.to_dict() for e in encounters]
    
    if data_type in ('metrics', 'all'):
        metrics_repo = MetricsRepository(db)
        # Get various metrics
        data['metrics'] = {
            'census_history': metrics_repo.get_census_history(30),
        }
    
    output_path = Path(output)
    
    if format == 'json':
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    console.print(f"\n[green]✓[/green] Export complete")


@cli.group()
def analyze():
    """Analytics and reporting commands."""
    pass


@analyze.command('compliance')
@click.option('--facility-id', required=True, help='Facility identifier')
@click.pass_context
def analyze_compliance(ctx, facility_id):
    """Generate compliance report."""
    from cah_engine.integration.compliance_validator import (
        CAHComplianceValidator,
        ReportingPeriod,
    )
    from cah_engine.core.models import FacilitySnapshot
    
    console.print(f"\n[bold]Generating compliance report for:[/bold] {facility_id}")
    
    db = get_database(ctx.obj['db_path'])
    enc_repo = EncounterRepository(db)
    
    # Get recent encounters
    encounters = enc_repo.get_recent(days=365)
    
    # Create reporting period
    period = ReportingPeriod()
    for enc in encounters:
        period.add_encounter(enc)
    
    # Create current snapshot (simplified)
    snapshot = FacilitySnapshot(
        facility_id=facility_id,
        timestamp=datetime.now(),
        staffed_beds=25,
        occupied_beds=len(enc_repo.get_active()),
    )
    
    # Generate report
    validator = CAHComplianceValidator()
    report = validator.generate_report(facility_id, snapshot, period)
    
    # Display results
    status_style = "green" if report.is_compliant else "red"
    console.print(Panel(
        f"[bold]Overall Status:[/bold] [{status_style}]{report.overall_status.value.upper()}[/{status_style}]\n\n"
        f"[bold]Key Metrics:[/bold]\n"
        f"  Staffed Beds: {report.current_staffed_beds}\n"
        f"  Average LOS: {report.average_los_hours:.1f} hours\n"
        f"  LOS Compliance: {report.los_compliance_rate:.1f}%\n",
        title=f"Compliance Report - {facility_id}",
    ))
    
    if report.issues:
        console.print("\n[bold red]Critical Issues:[/bold red]")
        for issue in report.issues:
            console.print(f"  [red]•[/red] {issue.message}")
            console.print(f"    Citation: {issue.citation}")
    
    if report.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in report.warnings:
            console.print(f"  [yellow]•[/yellow] {warning.message}")
    
    # Save report
    comp_repo = ComplianceRepository(db)
    comp_repo.save_report(facility_id, report.to_dict())
    console.print(f"\n[green]✓[/green] Report saved")


@analyze.command('gaps')
@click.option('--facility-id', required=True, help='Facility identifier')
@click.pass_context
def analyze_gaps(ctx, facility_id):
    """Perform gap analysis."""
    from cah_engine.analytics.gap_analyzer import GapAnalyzer
    
    console.print(f"\n[bold]Performing gap analysis for:[/bold] {facility_id}")
    
    db = get_database(ctx.obj['db_path'])
    cost_repo = CostReportRepository(db)
    
    metrics = cost_repo.get_by_provider(facility_id)
    
    if not metrics:
        console.print("[red]No cost report data found. Import cost report first.[/red]")
        return
    
    analyzer = GapAnalyzer()
    report = analyzer.analyze_metrics(metrics)
    
    # Display results
    table = Table(title="Performance Gaps")
    table.add_column("Metric", style="cyan")
    table.add_column("Current", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Gap", justify="right")
    table.add_column("Priority")
    
    for gap in report.gaps:
        gap_str = f"{gap.gap:+.1f}" if gap.gap < 0 else f"+{gap.gap:.1f}"
        priority_style = "red" if gap.priority == 1 else "yellow" if gap.priority == 2 else ""
        
        table.add_row(
            gap.metric_name,
            f"{gap.current_value:.1f}",
            f"{gap.target_value:.1f}",
            gap_str,
            f"[{priority_style}]P{gap.priority}[/{priority_style}]" if priority_style else f"P{gap.priority}",
        )
    
    console.print(table)
    
    if report.total_financial_gap > 0:
        console.print(f"\n[bold]Estimated Annual Financial Gap:[/bold] ${report.total_financial_gap:,.0f}")
    
    if report.priority_actions:
        console.print("\n[bold]Priority Actions:[/bold]")
        for i, action in enumerate(report.priority_actions[:5], 1):
            console.print(f"  {i}. {action}")


@analyze.command('forecast')
@click.option('--days', default=7, help='Forecast horizon in days')
@click.pass_context
def forecast_census(ctx, days):
    """Generate census forecast."""
    from cah_engine.analytics.predictive import CensusForecaster
    
    console.print(f"\n[bold]Generating {days}-day census forecast[/bold]")
    
    db = get_database(ctx.obj['db_path'])
    metrics_repo = MetricsRepository(db)
    
    # Get historical census
    history = metrics_repo.get_census_history(days=365)
    
    if len(history) < 30:
        console.print("[yellow]Insufficient data for forecasting. Need at least 30 days.[/yellow]")
        return
    
    # Train model
    forecaster = CensusForecaster()
    forecaster.train([(d, float(c)) for d, c in history])
    
    # Generate forecast
    result = forecaster.predict(horizon=days)
    
    # Display
    table = Table(title="Census Forecast")
    table.add_column("Date", style="cyan")
    table.add_column("Forecast", justify="right")
    table.add_column("Range (80%)", justify="right")
    
    for i, forecast_date in enumerate(result.dates):
        table.add_row(
            forecast_date.strftime("%Y-%m-%d"),
            f"{result.point_forecast[i]:.1f}",
            f"{result.lower_bound[i]:.1f} - {result.upper_bound[i]:.1f}",
        )
    
    console.print(table)


@cli.group()
def decision():
    """Decision support tools."""
    pass


@decision.command('transfer')
@click.option('--diagnosis', required=True, help='Principal diagnosis code')
@click.option('--acuity', type=int, default=3, help='ESI acuity level (1-5)')
@click.option('--age', type=int, default=65, help='Patient age')
@click.pass_context
def transfer_decision(ctx, diagnosis, acuity, age):
    """Get transfer recommendation."""
    from cah_engine.decision.transfer_advisor import (
        TransferAdvisor,
        PatientPresentation,
        create_default_facility,
    )
    
    console.print(f"\n[bold]Transfer Decision Support[/bold]")
    console.print(f"  Diagnosis: {diagnosis}")
    console.print(f"  Acuity: ESI {acuity}")
    console.print(f"  Age: {age}")
    
    # Create presentation
    presentation = PatientPresentation(
        patient_id="eval_patient",
        presentation_time=datetime.now(),
        chief_complaint="",
        principal_diagnosis=diagnosis,
        acuity_level=acuity,
        age=age,
    )
    
    # Get recommendation
    facility = create_default_facility()
    advisor = TransferAdvisor(facility)
    recommendation = advisor.evaluate(presentation)
    
    # Display
    rec_style = "green" if recommendation.recommendation == "admit" else "yellow" if recommendation.recommendation == "observe" else "red"
    
    console.print(Panel(
        f"[bold]Recommendation:[/bold] [{rec_style}]{recommendation.recommendation.upper()}[/{rec_style}]\n\n"
        f"[bold]Confidence:[/bold] {recommendation.confidence:.0%}\n\n"
        f"[bold]Rationale:[/bold]\n{recommendation.rationale}\n\n"
        f"[bold]Risk Score:[/bold] {recommendation.risk_score:.0f}/100\n\n"
        f"[bold]EMTALA Compliant:[/bold] {'Yes' if recommendation.emtala_compliant else 'No'}",
        title="Transfer Advisor",
    ))
    
    if recommendation.contributing_factors:
        console.print("\n[bold]Contributing Factors:[/bold]")
        for factor in recommendation.contributing_factors:
            console.print(f"  • {factor}")


@cli.command()
@click.pass_context
def dashboard(ctx):
    """Display interactive dashboard summary."""
    print_banner()
    
    db = get_database(ctx.obj['db_path'])
    enc_repo = EncounterRepository(db)
    
    # Current census
    active = enc_repo.get_active()
    
    console.print(Panel(
        f"[bold cyan]Current Census:[/bold cyan] {len(active)} patients\n"
        f"[bold cyan]Active Encounters:[/bold cyan] {len(active)}\n",
        title="Dashboard",
    ))
    
    # Recent statistics
    stats = enc_repo.get_los_statistics(
        start=datetime.now() - timedelta(days=30)
    )
    
    console.print(f"\n[bold]30-Day Statistics:[/bold]")
    console.print(f"  Discharges: {stats['count']}")
    console.print(f"  Avg LOS: {stats['average']:.1f} hours")
    
    # Encounter breakdown
    counts = enc_repo.count_by_type(
        start=datetime.now() - timedelta(days=30)
    )
    
    if counts:
        console.print(f"\n[bold]Encounters by Type:[/bold]")
        for enc_type, count in counts.items():
            console.print(f"  {enc_type.value}: {count}")


# Alias for CLI
app = cli


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == '__main__':
    main()

