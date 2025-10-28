from __future__ import annotations

import logging
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


class PackageInstallationLogger(Action):
    """Log information about packages that were installed or removed."""
    
    def verify(self):
        """Verify that the action can be executed."""
        log.debug("Verifying package installation logger action")
        self._verified = True
    
    def execute(self):
        """Log information about installed and removed packages."""
        log.info("=== Conda Package Installation Summary ===")
        
        # Log installed packages
        if self.link_precs:
            log.info(f"Installed {len(self.link_precs)} package(s):")
            for prec in self.link_precs:
                log.info(f"  + {prec.name} {prec.version} ({prec.build})")
        else:
            log.info("No packages were installed")
        
        # Log removed packages
        if self.unlink_precs:
            log.info(f"Removed {len(self.unlink_precs)} package(s):")
            for prec in self.unlink_precs:
                log.info(f"  - {prec.name} {prec.version} ({prec.build})")
        else:
            log.info("No packages were removed")
        
        # Log update specifications
        if self.update_specs:
            log.info(f"Updated {len(self.update_specs)} package(s):")
            for spec in self.update_specs:
                log.info(f"  ~ {spec}")
        
        # Log remove specifications
        if self.remove_specs:
            log.info(f"Remove specifications: {self.remove_specs}")
        
        # Log neutered specifications
        if self.neutered_specs:
            log.info(f"Neutered specifications: {self.neutered_specs}")
        
        log.info("=== End Package Installation Summary ===")
    
    def reverse(self):
        """Reverse the action if it fails."""
        log.debug("Reversing package installation logger action")
    
    def cleanup(self):
        """Clean up any resources created during the action."""
        log.debug("Cleaning up package installation logger action")


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
    """Register post-transaction hooks for package installation logging."""
    yield plugins.CondaPostTransactionAction(
        name="package-installation-logger",
        action=PackageInstallationLogger,
    )
