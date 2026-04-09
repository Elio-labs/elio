import typer

# This is the single Typer app.
# main.py, commands.py all import this object and register their callbacks on it.
app = typer.Typer(
    name="elio",
    help="Unified AI CLI",
    add_completion=False,
    rich_markup_mode="rich",
)