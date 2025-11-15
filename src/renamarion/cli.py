import time
from pathlib import Path
from dataclasses import dataclass, field
import click
from colorama import Fore, Style
from typing import Literal, Set, Any, Dict, Type
from abc import ABC, abstractmethod


class MatcherAction(ABC):
    @abstractmethod
    def matches(self, item_name: str) -> bool: ...

    @classmethod
    @abstractmethod
    def replace(cls, item_name: str) -> str: ...

    def __init__(self, name: str):
        self.name = name

    # def __contains__(self, item_name: str) -> bool:
    #     return self.matches(item_name)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(str(self))


class MultiProblems:
    def __init__(self, problems: Set[str | MatcherAction]):
        self.problems = problems

    def __str__(self):
        return str(sorted([self.problems]))

    def __repr__(self) -> str:
        return self.__str__()

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, multi_problem: object) -> bool:
        if not isinstance(multi_problem, MultiProblems):
            raise NotImplementedError
        return self.__hash__() == multi_problem.__hash__()


MatchMapping = Dict[str | MatcherAction, str | Type[MatcherAction]]


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
    problems: Set[str | MatcherAction]


@dataclass
class FileSystemData:
    scanned_items: list[FileSystemItem] = field(default_factory=list)

    def add(
        self,
        type: Literal["file", "directory"],
        invalid: bool,
        path: Path,
        problems: Set[str | MatcherAction],
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
            [MultiProblems(item.problems) for item in self.problematic_files]
        )
        return {
            problem_key: [
                item
                for item in self.problematic_files
                if MultiProblems(item.problems) == problem_key
            ]
            for problem_key in unique_problems
        }

    @property
    def problematic_directories_types(self):
        unique_problems = set(
            [MultiProblems(item.problems) for item in self.problematic_directories]
        )
        return {
            problem_key: [
                item
                for item in self.problematic_directories
                if MultiProblems(item.problems) == problem_key
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
    forbidden_characters_mapping: MatchMapping,
):
    invalidity, problems = is_item_invalid(item_name, forbidden_characters_mapping)
    data.add(
        type=item_type,
        invalid=invalidity,
        path=root / item_name,
        problems=problems,
    )


def is_item_invalid(
    item_name: str,
    forbidden_characters_mapping: MatchMapping,
) -> tuple[bool, Set[str | MatcherAction]]:
    problems = set(
        [
            char
            for char in forbidden_characters_mapping.keys()
            if (isinstance(char, str) and char in item_name)
            or isinstance(char, MatcherAction)
            and char.matches(item_name)
        ]
    )

    # problems = set(
    #     [char for char in forbidden_characters_mapping.keys() if char in item_name]
    # )
    # if item_name.endswith((",", " ")):
    #     problems.add("termination")
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

    def format_mapping_results(mapping: dict[MultiProblems, int]):
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
                renamed_path = get_item_renamed_path(item, forbidden_characters_mapping)
                agreed = click.confirm(
                    f" - {Fore.BLUE}{item.type.capitalize()} : {Fore.YELLOW}{item.path}{Fore.BLUE} "
                    "will be renamed into "
                    f"{Fore.YELLOW}{renamed_path}{Fore.BLUE}. "
                    f"{Fore.LIGHTMAGENTA_EX}Do you agree to proceed ?{Fore.RESET}",
                    prompt_suffix="",
                    default=True,
                    show_default=False,
                )

                if agreed:
                    item.path.rename(renamed_path)
                    click.echo(
                        f"{Fore.GREEN}✅ Renamed {Fore.YELLOW}{renamed_path}{Fore.GREEN} succesfully.{Fore.RESET}"
                    )
                else:
                    click.echo(f"{Fore.RED}🚫 Did not rename. {Fore.RESET}")


def get_item_renamed_path(
    item: FileSystemItem, forbidden_characters_mapping: MatchMapping
):
    if not item.invalid:
        return item.path
    new_path = item.path
    for problem in item.problems:
        if isinstance(problem, str):
            new_path = new_path.parent / str(new_path.name).replace(
                problem, forbidden_characters_mapping[problem]
            )

            # problem.
            # new_path = new_path.parent / str(new_path.name).rstrip(" ").rstrip(
            #     ","
            # ).rstrip(" ")
        elif isinstance(problem, MatcherAction):
            new_path = new_path.parent / problem.replace(new_path.name)

            # new_path = new_path.parent / str(new_path.name).replace(
            #     problem, forbidden_characters_mapping[problem]
            # )
    return new_path


def get_forbidden_characters():
    forbidden_mapping: MatchMapping

    class Termination(MatcherAction):
        def matches(self, item_name: str):
            return item_name.endswith((",", " ", ".", "\uf022"))

        @classmethod
        def replace(cls, item_name: str):
            return (
                item_name.rstrip(" ")
                .rstrip(",")
                .rstrip(".")
                .rstrip("\uf022")
                .rstrip(" ")
            )

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
        "/": "_",
        "\r": "",
        Termination("termination"): Termination,
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
        if any([c in char for c in forbidden_mapping.keys()]):
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
            type=click.Choice(forbidden_mapping.keys()),
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
