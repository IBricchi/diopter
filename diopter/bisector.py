import logging
import math
from pathlib import Path
from typing import Callable, Optional, TypeVar

from ccbuilder import Builder, BuildException, Commit, CompilerProject, Repo, Revision

S = TypeVar("S")


class BisectionException(Exception):
    pass


def find_cached_revisions(project: CompilerProject, cache_prefix: Path) -> list[Commit]:
    """Find and return all cached revisions of `project` in `cache_prefix`.

    Args:
        project (CompilerProject): Which projects cached revisions to get.
        cache_prefix (Path): Path to the compiler cache.

    Returns:
        list[Commit]: List of all cached revisions for `project`.
    """
    match project:
        case CompilerProject.GCC:
            compiler_name = "gcc"
        case CompilerProject.LLVM:
            compiler_name = "clang"

    compilers: list[Commit] = []

    for entry in Path(cache_prefix).iterdir():
        if entry.is_symlink() or not entry.stem.startswith(compiler_name):
            continue
        if not (entry / "bin" / compiler_name).exists():
            continue
        rev: Commit = str(entry).split("-")[-1]
        compilers.append(rev)
    return compilers


def find_sorted_cached_commits_from_range(
    good_rev: Revision,
    bad_rev: Revision,
    project: CompilerProject,
    repo: Repo,
    cache_prefix: Path,
) -> list[Commit]:
    """Return all cached commits that are in the range R=[good_rev, bad_rev] such that
    R[i+1] is ancestor of R[i].

    Args:
        good_rev (Revision): good_rev
        bad_rev (Revision): bad_rev
        project (CompilerProject): project
        repo (Repo): Repository for `project`
        cache_prefix (Path): Path to the cache.

    Returns:
        list[Commit]: All cached commits in [good_rev, bad_rev] ordered via the ancestor relation.
    """
    possible_revs = repo.direct_first_parent_path(good_rev, bad_rev)

    cached_revs = find_cached_revisions(project, cache_prefix)
    cached_revs = [r for r in cached_revs if r in possible_revs]

    # Create enumeration dict to sort cached_revs with
    sort_dict = dict((r, v) for v, r in enumerate(possible_revs))
    cached_revs = sorted(cached_revs, key=lambda x: sort_dict[x])
    return cached_revs


def _get_midpoint_after_failure(
    bad_rev: Revision,
    good_rev: Revision,
    midpoint: Revision,
    failed_to_build_counter: int,
    repo: Repo,
    max_failed_builds: int = 3,
) -> Commit:
    if failed_to_build_counter >= max_failed_builds:
        raise BisectionException(
            "Failed too many times in a row while bisecting. Aborting bisection..."
        )
    if failed_to_build_counter % 2 == 0:
        # Get size of range
        range_size = len(repo.direct_first_parent_path(midpoint, bad_rev))

        # Move 10% towards the last bad
        step = max(int(0.9 * range_size), 1)
        midpoint = repo.rev_to_commit(f"{bad_rev}~{step}")
    else:
        # Symmetric to case above but jumping 10% into the other direction i.e 20% from our position.
        range_size = len(repo.direct_first_parent_path(good_rev, midpoint))
        step = max(int(0.2 * range_size), 1)
        midpoint = repo.rev_to_commit(f"{midpoint}~{step}")
    return midpoint


def _terminate(guaranteed_termination_counter: int) -> bool:
    if guaranteed_termination_counter >= 20:
        logging.warning(
            "Failed too many times in a row while bisecting. Aborting bisection..."
        )
        return True
    return False


class Bisector:
    def __init__(self, bldr: Builder):
        self.bldr = bldr
        return

    def bisect(
        self,
        state: S,
        test: Callable[[Commit, S, Builder], Optional[bool]],
        bad_rev: Revision,
        good_rev: Revision,
        project: CompilerProject,
        repo: Repo,
    ) -> Optional[Commit]:
        """Bisect between `bad_rev` and `good_rev` based on the provided `test` function.
        `test(bad_rev, state, bldr)` must be True.
        `test(good_rev, state, bldr)` must be False.

        Args:
            self:
            state (S): Some kind of state that is required to run the `test`.
            test (Callable[[Commit, S, Builder], Optional[bool]]): Interestingness test>
            bad_rev (Revision): Revision that shows the initial unwanted behaviour, defined in `test`.
            good_rev (Revision): Revision that shows the initial correct behaviour.
            project (CompilerProject): Which project on bisect in.
            repo (Repo): Repository for the `project`.

        Returns:
            Optional[Commit]: The bisection commit that introduced the behaviour
        """

        # sanitize revs
        good_commit = repo.rev_to_commit(good_rev)
        bad_commit = repo.rev_to_commit(bad_rev)

        # Make sure there is a direct path between the two
        # commits. If none is found or the good commit would
        # 'land on top', we abort.
        if not repo.is_ancestor(good_commit, bad_commit):
            bca = repo.get_best_common_ancestor(good_commit, bad_commit)
            test_res: Optional[bool] = test(bca, state, self.bldr)
            match test_res:
                case False:
                    good_commit = bca
                case True:
                    logging.info("Best common ancestor is interesting. Can't bisect.")
                    return None
                case None:
                    logging.info("Test for best common ancestor failed. Can't bisect.")
                    return None

        try:
            good_commit, bad_commit = self._in_cache_path_bisection(
                state=state,
                test=test,
                bad_commit=bad_commit,
                good_commit=good_commit,
                project=project,
                repo=repo,
            )
            logging.info(f"{good_commit=} {bad_commit=}")
            if bisection_commit := self._normal_path_bisection(
                state=state,
                test=test,
                bad_commit=bad_commit,
                good_commit=good_commit,
                project=project,
                repo=repo,
            ):
                # Check if the result is correct
                pre_bisection_commit = repo.rev_to_commit(f"{bisection_commit}~")
                bisection_res = test(bisection_commit, state, self.bldr)
                pre_bisection_res = test(pre_bisection_commit, state, self.bldr)
                if (bisection_res == True) and (pre_bisection_res == False):
                    return bisection_commit
                logging.warning("Bisection check failed!")
                return None
            return None
        except BisectionException as e:
            logging.warning(e)
            return None

    def _in_cache_path_bisection(
        self,
        state: S,
        test: Callable[[Commit, S, Builder], Optional[bool]],
        bad_commit: Commit,
        good_commit: Commit,
        project: CompilerProject,
        repo: Repo,
    ) -> tuple[Commit, Commit]:

        cached_commits = find_sorted_cached_commits_from_range(
            good_commit, bad_commit, project, repo, self.bldr.cache_prefix
        )

        logging.info(f"Bisecting in cache...")
        midpoint = ""
        old_midpoint = ""
        while True:
            logging.info(
                f"{len(cached_commits): 4}, bad: {bad_commit}, good: {good_commit}"
            )
            if len(cached_commits) == 0:
                break
            midpoint_idx = len(cached_commits) // 2
            old_midpoint = midpoint
            midpoint = cached_commits[midpoint_idx]
            if old_midpoint == midpoint:
                break

            test_res: Optional[bool] = test(midpoint, state, self.bldr)

            match test_res:
                case True:
                    bad_commit = midpoint
                    cached_commits = cached_commits[midpoint_idx + 1 :]
                case False:
                    good_commit = midpoint
                    cached_commits = cached_commits[:midpoint_idx]
                case None:
                    # Test failed.
                    cached_commits.remove(midpoint)

        return good_commit, bad_commit

    def _normal_path_bisection(
        self,
        state: S,
        test: Callable[[Commit, S, Builder], Optional[bool]],
        bad_commit: Commit,
        good_commit: Commit,
        project: CompilerProject,
        repo: Repo,
    ) -> Optional[Commit]:

        logging.info("Starting normal bisection...")
        len_region = len(repo.direct_first_parent_path(good_commit, bad_commit))
        logging.info(f"Bisecting for approx. {math.ceil(math.log2(len_region))} steps")
        midpoint = ""
        old_midpoint = ""
        test_failed = False
        failed_to_build_counter = 0

        guaranteed_termination_counter = 0
        while True:
            if not test_failed:
                old_midpoint = midpoint
                midpoint = repo.next_bisection_commit(good_commit, bad_commit)
                failed_to_build_counter = 0
                guaranteed_termination_counter = 0
                if midpoint == "" or midpoint == old_midpoint:
                    break
            else:
                midpoint = _get_midpoint_after_failure(
                    bad_commit, good_commit, midpoint, failed_to_build_counter, repo
                )
                if _terminate(guaranteed_termination_counter):
                    return None
                guaranteed_termination_counter += 1
                failed_to_build_counter += 1
                test_failed = False

            logging.info(f"Midpoint: {midpoint}")

            try:
                _ = self.bldr.build(project, midpoint)
                test_res: Optional[bool] = test(midpoint, state, self.bldr)
            except BuildException as e:
                logging.warning(
                    f"Could not build {project.to_string()} {midpoint}!: {e}"
                )
                test_failed = True
                continue

            match test_res:
                case True:
                    bad_commit = midpoint
                case False:
                    good_commit = midpoint
                case None:
                    test_failed = True

        logging.info(f"Bisection result: {bad_commit}")
        return bad_commit
