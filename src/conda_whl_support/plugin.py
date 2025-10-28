from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from conda import plugins
from conda.core.path_actions import Action

if TYPE_CHECKING:
    from typing import Generator


log = logging.getLogger(__name__)

def add_whl_support(command: str) -> None:
    """ Implement support for installing wheels in conda """
    log.debug("Inside add_whl_support")

    # add .whl to KNOWN EXTENSIONS
    import conda.common.path
    conda.common.path.KNOWN_EXTENSIONS = (".conda", ".tar.bz2", ".json", ".jlap", ".json.zst", ".whl")

    # Patch the extract_tarball function
    # Add support for extracting wheels with in-line creation of conda metadata files
    import conda.core.path_actions
    if conda.core.path_actions.extract_tarball.__module__ != __name__:
        from .extract_whl_or_tarball import extract_whl_or_tarball
        conda.core.path_actions.extract_tarball = extract_whl_or_tarball

    # Allow the creation of prefix record JSON files for .whl files
    import conda.core.prefix_data
    conda.core.prefix_data.CONDA_PACKAGE_EXTENSIONS = (".tar.bz2", ".conda", ".whl")

    # Skip the check that name, version, build matches filename in prefix record json
    from conda.core.prefix_data import PrefixData
    if PrefixData._load_single_record.__module__ != __name__:
        from .patched_load import _load_single_record
        PrefixData._load_single_record = _load_single_record

    return


class HiddenPackageCleaner(Action):
    """Clean up conda-meta files for hidden packages (those starting with _c)."""
    
    def verify(self):
        """Verify that the action can be executed."""
        log.debug("Verifying hidden package cleaner action")
        self._verified = True
    
    def execute(self):
        """Check for _c packages and delete their conda-meta files."""
        # Check installed packages for _c packages
        if self.link_precs:
            for prec in self.link_precs:
                # Check if this is a _c package and delete its conda-meta file
                if prec.name.startswith('_c'):
                    self._delete_conda_meta_file(prec)
    
    def _delete_conda_meta_file(self, prec):
        """Delete the conda-meta file for a _c package."""
        try:
            # Construct the conda-meta file path
            meta_filename = f"{prec.name}-{prec.version}-{prec.build}.json"
            meta_path = os.path.join(self.target_prefix, "conda-meta", meta_filename)
            
            if os.path.exists(meta_path):
                os.remove(meta_path)
                log.info(f"  Deleted conda-meta file: {meta_filename}")
            else:
                log.warning(f"  Conda-meta file not found: {meta_filename}")
        except Exception as e:
            log.error(f"  Failed to delete conda-meta file for {prec.name}: {e}")
    
    def reverse(self):
        """Reverse the action if it fails."""
        log.debug("Reversing hidden package cleaner action")
    
    def cleanup(self):
        """Clean up any resources created during the action."""
        log.debug("Cleaning up hidden package cleaner action")


@plugins.hookimpl
def conda_pre_commands() -> Generator[plugins.CondaPreCommand, None, None]:
    yield plugins.CondaPreCommand(
        name="conda-whl-support",
        action=add_whl_support,
        run_for={
            "create",
            "install",
            "remove",
            "rename",
            "update",
            "env_create",
            "env_update",
            "list",
        },
    )


@plugins.hookimpl
def conda_post_transaction_actions() -> Generator[plugins.CondaPostTransactionAction, None, None]:
    """Register post-transaction hooks for hidden package cleanup."""
    yield plugins.CondaPostTransactionAction(
        name="hidden-package-cleaner",
        action=HiddenPackageCleaner,
    )
