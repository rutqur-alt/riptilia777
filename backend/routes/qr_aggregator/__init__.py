"""QR Aggregator routes.

This package was created as part of the architecture isolation work.

`legacy.py` currently contains the original monolithic implementation.
Incremental refactors should extract logic into dedicated modules and keep this
package's public API stable.

The rest of the backend imports `router` from `routes.qr_aggregator`.
"""

from .router import router  # re-export

# Import modules for side effects: they register routes on `router`.
from . import provider_routes as _provider_routes  # noqa: F401
from . import legacy as _legacy  # noqa: F401
