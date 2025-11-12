import time
from pathlib import Path
from dataclasses import dataclass, field
import click
from colorama import Fore, Style
from typing import Literal, Set, Any


CYCLE_CHAR = "."
CYCLE_MAX_STAGE = 20
CYCLE_STAGE = 0
CYCLE_MODE = True
CYCLE_LAST_UPDATE = time.time()
CYCLE_UPDATE_RATE = 1 / 60  # 60 Hz
CYCLE_PREFIX = "Scanning : "


def cycle():
    global CYCLE_STAGE, CYCLE_MODE, CYCLE_LAST_UPDATE
    current_time = time.time()
    if current_time - CYCLE_LAST_UPDATE < CYCLE_UPDATE_RATE:
        return
    CYCLE_LAST_UPDATE = current_time

    if CYCLE_MODE:
        CYCLE_STAGE += 1
        if CYCLE_STAGE > CYCLE_MAX_STAGE:
            CYCLE_STAGE = CYCLE_MAX_STAGE
            CYCLE_MODE = not CYCLE_MODE
    else:
        CYCLE_STAGE -= 1
        if CYCLE_STAGE < 0:
            CYCLE_STAGE = 0
            CYCLE_MODE = not CYCLE_MODE

    print(
        f"{CYCLE_PREFIX}{CYCLE_CHAR * CYCLE_STAGE}{' ' * (CYCLE_MAX_STAGE - CYCLE_STAGE)}",
        end="\r",
    )


def cycle_end():
    print((" " * len(CYCLE_PREFIX)) + " " * (CYCLE_MAX_STAGE + 1))


@dataclass
class FileSystemItem:
    type: Literal["file", "directory"]
    invalid: bool
    path: Path
    problems: Set[str]


@dataclass
class FileSystemData:
    scanned_items: list[FileSystemItem] = field(default_factory=list)

    def add(
        self,
        type: Literal["file", "directory"],
        invalid: bool,
        path: Path,
        problems: Set[str],
    ):
        self.scanned_items.append(
            FileSystemItem(type=type, invalid=invalid, path=path, problems=problems)
        )

    @property
    def directories(self):
        return [item for item in self.scanned_items if item.type == "directory"]

    @property
    def files(self):
        return [item for item in self.scanned_items if item.type == "file"]

    @property
    def directories_count(self):
        return len(self.directories)

    @property
    def file_count(self):
        return len(self.files)

    @property
    def problematic_files(self):
        return [item for item in self.files if item.invalid]

    @property
    def problematic_directories(self):
        return [item for item in self.directories if item.invalid]

    @property
    def problematic_files_count(self):
        return len(self.problematic_files)

    @property
    def problematic_directories_count(self):
        return len(self.problematic_directories)

    @property
    def problematic_files_types(self):
        unique_problems = set(
            [str(sorted(item.problems)) for item in self.problematic_files]
        )
        return {
            problem_key: [
                item
                for item in self.problematic_files
                if str(sorted(item.problems)) == problem_key
            ]
            for problem_key in unique_problems
        }

    @property
    def problematic_directories_types(self):
        unique_problems = set(
            [str(sorted(item.problems)) for item in self.problematic_directories]
        )
        return {
            problem_key: [
                item
                for item in self.problematic_directories
                if str(sorted(item.problems)) == problem_key
            ]
            for problem_key in unique_problems
        }

    @property
    def problematic_directories_types_counts(self):
        return {
            problem_key: len(items)
            for problem_key, items in self.problematic_directories_types.items()
        }

    @property
    def problematic_files_types_counts(self):
        return {
            problem_key: len(items)
            for problem_key, items in self.problematic_files_types.items()
        }


def parse_item(
    root: Path,
    item_name: str,
    item_type: Literal["file", "directory"],
    data: FileSystemData,
    forbidden_characters_mapping: dict[str, str],
):
    invalidity, problems = is_item_invalid(item_name, forbidden_characters_mapping)
    data.add(
        type=item_type,
        invalid=invalidity,
        path=root / item_name,
        problems=problems,
    )


def is_item_invalid(item_name: str, forbidden_characters_mapping: dict[str, str]):
    problems = set(
        [char for char in forbidden_characters_mapping.keys() if char in item_name]
    )
    if item_name.endswith((",", " ")):
        problems.add("termination")
    if len(problems):
        return True, problems
    return False, set()


@click.command()
@click.option("-p", "--path", default=Path.home(), help="Path")
def run(path: str):
    root = Path(path)

    click.echo(
        f"{Fore.BLUE}The path to the selected folder is {Fore.LIGHTYELLOW_EX}{root}{Style.RESET_ALL}"
    )
    status = click.confirm(
        f"❓ {Fore.LIGHTMAGENTA_EX}Is this path the one you planned ❓{Style.RESET_ALL}"
    )
    if not status:
        return

    forbidden_characters_mapping = get_forbidden_characters()
    data = FileSystemData()
    for current_folder, dirs, files in root.walk():
        for directory in dirs:
            parse_item(
                current_folder,
                directory,
                "directory",
                data,
                forbidden_characters_mapping,
            )

        for file in files:
            parse_item(
                current_folder,
                file,
                "file",
                data,
                forbidden_characters_mapping,
            )

        cycle()
    cycle_end()

    click.echo(
        f"{Fore.BLUE}Scanned {Fore.YELLOW}{data.file_count}{Fore.BLUE} total files.{Style.RESET_ALL}"
    )
    click.echo(
        f"{Fore.BLUE}Scanned {Fore.YELLOW}{data.directories_count}{Fore.BLUE} total repositories.{Style.RESET_ALL}"
    )
    click.echo(
        f"{Fore.BLUE}Found {Fore.YELLOW}{data.problematic_files_count}{Fore.BLUE} problematic files.{Style.RESET_ALL}"
    )
    click.echo(
        f"{Fore.BLUE}Found {Fore.YELLOW}{data.problematic_directories_count}{Fore.BLUE} "
        f"problematic repositories.{Style.RESET_ALL}"
    )

    def format_mapping_results(mapping: dict[str, Any]):
        return "\n".join(
            [
                f" - {Fore.GREEN}{key}{Fore.BLUE} contains {Fore.CYAN}{value}{Fore.RESET}"
                for key, value in mapping.items()
            ]
        )

    click.echo(
        "Problems for files : \n"
        + format_mapping_results(data.problematic_files_types_counts)
    )
    click.echo(
        "Problems for directories : \n"
        + format_mapping_results(data.problematic_directories_types_counts)
    )

    click.echo(f"\n{Fore.BLUE}Problems Resolution :{Fore.RESET}\n")
    for problem_dictionnary in [
        data.problematic_directories_types,
        data.problematic_files_types,
    ]:
        for problem_name, items in problem_dictionnary.items():
            click.echo(f"{Fore.BLUE}Problem {Fore.GREEN}{problem_name}{Fore.RESET}")
            for item in items:
                click.prompt(
                    f" - {Fore.BLUE}{item.type.capitalize()} : {Fore.YELLOW}{item.path}{Fore.BLUE} will be renamed into "
                    f"{Fore.YELLOW}{get_item_renamed_path(item, forbidden_characters_mapping)}{Fore.BLUE}. "
                    f"{Fore.LIGHTMAGENTA_EX}Do you agree to proceed ?{Fore.RESET}",
                    prompt_suffix="",
                    default="",
                    show_default=False,
                )


def get_item_renamed_path(
    item: FileSystemItem, forbidden_characters_mapping: dict[str, str]
):
    if not item.invalid:
        return item.path
    new_path = item.path
    for problem in item.problems:
        if problem == "termination":
            new_path = new_path.parent / str(new_path.name).rstrip(" ").rstrip(
                ","
            ).rstrip(" ")
        else:
            new_path = new_path.parent / str(new_path.name).replace(
                problem, forbidden_characters_mapping[problem]
            )
    return new_path


def get_forbidden_characters():
    forbidden_characters = [
        "<",
        ">",
        ":",
        '"',
        "|",
        "?",
        "*",
        "\uf022",
        "\\",
        "\r",
    ]
    forbidden_mapping = {k: k for k in forbidden_characters}
    forbidden_mapping = {
        "<": "(",
        ">": ")",
        ":": "-",
        '"': "-",
        "|": "_",
        "?": ".",
        "*": "x",
        "\uf022": "-",
        "\\": "_",
        "\r": "",
    }

    def format_characters():
        return "\n".join(
            [
                f" - {Fore.GREEN}{repr(key).replace("'", '')}{Fore.BLUE} will be converted to "
                f"{Fore.CYAN}{value}{Fore.RESET}"
                for key, value in forbidden_mapping.items()
            ]
        )

    def char_validation(char):
        if any([c in char for c in forbidden_characters]):
            raise ValueError(f"{Fore.BLUE}Forbidden character{Fore.RESET}")
        return str(char)

    while True:
        click.echo(f"Forbidden characters are :\n{format_characters()}\n")
        stop_loop = click.confirm(
            f"{Fore.LIGHTMAGENTA_EX}Do you find this to be ok ?{Fore.RESET}"
        )
        if stop_loop:
            break
        edit_source_char = click.prompt(
            f"{Fore.LIGHTMAGENTA_EX}What character to edit ?{Fore.RESET}",
            type=click.Choice(forbidden_characters),
        )
        while True:
            try:
                edit_destination_char = click.prompt(
                    f"{Fore.LIGHTMAGENTA_EX}What character to replace it with ?{Fore.RESET}",
                    value_proc=char_validation,
                )
                break
            except ValueError:
                click.echo(
                    f"{Fore.RED}Invalid input, as it contains a forbidden character, Please try again.{Fore.RESET}"
                )

        forbidden_mapping[edit_source_char] = edit_destination_char

    return forbidden_mapping
