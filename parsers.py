import argparse
import os


def config_parser(expected_entries: list[tuple]):
    parser = argparse.ArgumentParser(add_help=False)

    for _, path, desc in expected_entries:
        parser.add_argument("--" + ".".join(path), help=desc)
    parser.add_argument("--config", type=os.PathLike[str], help="Path to config.json")

    parser.add_argument(
        "-ll",
        "--log-level",
        type=str,
        choices=("debug", "info", "warning", "error", "critical"),
        help="Log level",
    )

    parser.add_argument(
        "--cores", help="Amount of build cores to use. Defaults to all.", type=int
    )

    return parser


def builder_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument(
        "-c", "--compiler", help="Which compiler project to use", nargs=1, type=str
    )

    parser.add_argument(
        "-r",
        "--revision",
        help="Which revision of the compiler project to use. Use 'trunk' to use the latest commit",
        nargs="+",
        type=str,
    )

    parser.add_argument(
        "--build-releases", help="Build release versions", action="store_true"
    )

    parser.add_argument(
        "--add-patches",
        help="Which patches to apply in addition to the ones found in patchDB",
        nargs="+",
        type=str,
    )

    parser.add_argument(
        "-f",
        "--force",
        help="Force build even if patch combo is known to be bad",
        action="store_true",
    )
    return parser


def patcher_parser():
    parser = argparse.ArgumentParser(add_help=False)

    mut_excl_group = parser.add_mutually_exclusive_group(required=True)

    # ====================
    mut_excl_group.add_argument(
        "--find-range",
        help="Try to find the range where a patch is required",
        action="store_true",
    )

    parser.add_argument(
        "-c",
        "--compiler",
        help="Which compiler project to use",
        nargs=1,
        type=str,
        required=True,
    )

    parser.add_argument(
        "-pr",
        "--patchable-revision",
        help="Which revision is patchable with the commit specified in --patch",
        type=str,
    )

    parser.add_argument(
        "--patch",
        help="Which revision is patchable with the commit specified in --patch",
        type=str,
    )
    # ====================
    mut_excl_group.add_argument(
        "--find-introducer",
        help="Try to find the introducer commit of a build failure.",
        action="store_true",
    )

    parser.add_argument(
        "-br", "--broken-revision", help="Which revision is borken", type=str
    )
    # ====================

    return parser


def generator_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("-a", "--amount", help="Amount of cases to generate.", type=int)

    parser.add_argument(
        "--interesting",
        help="If the generated case should be an interesting one.",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    parser.add_argument(
        "-t",
        "--targets",
        help="Project name and revision of compiler to use.",
        nargs="+",
        type=str,
    )

    parser.add_argument(
        "-tdol",
        "--targets-default-opt-levels",
        help="Default optimization levels for the target to be checked against.",
        nargs="+",
        default="3",
        type=str,
    )

    parser.add_argument(
        "-ac",
        "--additional-compiler",
        help="Additional compiler to compare the target against.",
        nargs="*",
        type=str,
    )

    parser.add_argument(
        "-acdol",
        "--additional-compilers-default-opt-levels",
        help="Default optimization levels for the additional compilers to be checked against.",
        nargs="+",
        default=["1", "2", "3", "s", "z"],
        type=str,
    )

    parser.add_argument(
        "-p",
        "--parallel",
        help="Run the search in parallel for --parallel processes. Works only in combination with --interesting.",
        type=int,
    )

    parser.add_argument(
        "-d", "--output-directory", help="Where the cases should be saved to.", type=str
    )

    return parser


def checker_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument(
        "-f", "--file", help="Which file to work on.", type=str, required=True
    )

    parser.add_argument("-m", "--marker", help="Marker to check for.", type=str)

    parser.add_argument(
        "-bad",
        "--bad-settings",
        help="Settings which are supposed to *not* eliminate the marker",
        nargs="+",
        type=str,
    )

    parser.add_argument(
        "-bsdol",
        "--bad-settings-default-opt-levels",
        help="Default optimization levels for the bad-settings to be checked against.",
        nargs="+",
        default=[],
        type=str,
    )

    parser.add_argument(
        "-good",
        "--good-settings",
        help="Settings which are supposed to eliminate the marker",
        nargs="+",
        type=str,
    )

    parser.add_argument(
        "-gsdol",
        "--good-settings-default-opt-levels",
        help="Default optimization levels for the good-settings to be checked against.",
        nargs="+",
        default=[],
        type=str,
    )

    return parser
