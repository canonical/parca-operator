"""# Overview.

This document explains how to integrate with the Parca charm where you wish to use Parca
as a store for profiles that are sent from a Parca Agent.

## Requirer Library usage

In this mode, your charm will be an application that needs to receive store configuration over the
relation in order that the workload can be configured to use a remote store for profiles.

To begin, start by importing the library and subscribing to some events:

```python
from charms.parca.v0.parca_store import (ParcaStoreEndpointRequirer, RemoveStoreEvent)

def __init__(self, *args):
    super().__init__(*args)
    # ...
    self.store_requirer = ParcaStoreEndpointRequirer(
        self, relation_name="external-parca-store-endpoint"
    )
    self.framework.observe(self.store_requirer.on.endpoints_changed, self._configure_store)
    self.framework.observe(self.store_requirer.on.remove_store, self._configure_store)
    # ...

def _configure_store(self, event):
    store_config = {} if isinstance(event, RemoveStoreEvent) else event.store_config
    self.application.configure(store_config=store_config)
    # ...
```

You can also fetch the store config at any time by using `self.store_requirer.config`.

## Provider library usage

In this mode, your charm will be the charm that provides the store capability. In order to use the
library, you must first import it, and initialise it in your charm's constructor:

```python
from charms.parca.v0.parca_store import ParcaStoreEndpointProvider

def __init__(self, *args):
    super().__init__(*args)
    # ...
    self.parca_store_endpoint = ParcaStoreEndpointProvider(
        charm = self,
        port = 7070,
        insecure = True
    )
    # ...
```

This will ensure that any client wishing to send profiles will be sent the application
address, along with the instruction to not use TLS for the connection.

If your store integrates with an ingress (such as Traefik), you will also need to pass
the `external_url` parameter:

```python
from charms.parca.v0.parca_store import ParcaStoreEndpointProvider

def __init__(self, *args):
    super().__init__(*args)
    # ...
    self.parca_store_endpoint = ParcaStoreEndpointProvider(
        charm = self,
        external_url = self._external_url(),
        port = 443,
        insecure = False
    )
    # ...
```

If your Parca store requires authentication with a bearer token, you can provide a method
that can be called for generating tokens on a per-relation basis:

```python
from charms.parca.v0.parca_store import ParcaStoreEndpointProvider

def __init__(self, *args):
    super().__init__(*args)
    # ...
    self.parca_store_endpoint = ParcaStoreEndpointProvider(
        charm = self,
        token_generator = self._bearer_token_generator
    )
    # ...
```

Where `self._bearer_token_generator` can be any `Callable` that returns a string.
"""

import ipaddress
import json
import socket
from typing import Callable
from urllib.parse import urlparse

import ops

# The unique Charmhub library identifier, never change it
LIBID = "6e4ff5ec91634160817322ba929d6cc6"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 4


DEFAULT_RELATION_NAME = "parca-store-endpoint"


class ParcaStoreEndpointProvider(ops.Object):
    """Profiling endpoint for Parca."""

    def __init__(
        self,
        charm,
        port: int = 7070,
        insecure: bool = False,
        external_url: str = None,
        token_generator: Callable = lambda: "",
        relation_name: str = DEFAULT_RELATION_NAME,
    ):
        """Construct a Parca profile store provider.

        If your charm exposes a Parca Store endpoint, the `ParcaStoreEndpointProvider` object
        enables your charm to easily communicate how to reach that endpoint.

        Args:
            charm: a `ops.CharmBase` object that manages this
                `ParcaStoreEndpointProvider` object. Typically this is `self` in the instantiating
                class.
            port: an optional integer that represents the port on which the Parca Store listens.
            insecure: an optional boolean that instructs clients whether or not to use TLS when
                connecting to the endpoint provided. Defaults to False, implying that by default
                TLS should be used.
            external_url: an optional string that represents the URL at which the Parca Store
                endpoint can be reached. Useful when the Parca Store implementation is behind
                an ingress or reverse proxy.
            token_generator: an optional method or lambda that can generate valid bearer tokens
                for the Parca Store. Defaults to a lambda that returns an empty string.
            relation_name: an optional string that denotes the name of the relation endpoint.
        """
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name
        self._token_generator = token_generator
        self._insecure = insecure
        self._external_url = external_url
        self._port = port

        self._app = self._charm.app

        events = self._charm.on[self._relation_name]
        self.framework.observe(events.relation_joined, self._set_relation_data)
        self.framework.observe(events.relation_changed, self._set_relation_data)
        self.framework.observe(self._charm.on.upgrade_charm, self._set_relation_data)

    def _set_relation_data(self, _):
        """Set relation data for each relation providing store connection details.

        Each time a profiling provider charm container is restarted it updates its own host address
        in the unit relation data for the Parca charm. The only argument specified is an event and
        it is ignored.
        """
        for relation in self._charm.model.relations[self._relation_name]:
            unit_ip = str(self._charm.model.get_binding(relation).network.bind_address)

            if self._external_url:
                parsed = urlparse(self._external_url)
                unit_address = parsed.hostname
            elif self._is_valid_unit_address(unit_ip):
                unit_address = unit_ip
            else:
                unit_address = socket.getfqdn()

            relation.data[self._app]["remote-store-address"] = f"{unit_address}:{self._port}"
            relation.data[self._app]["remote-store-bearer-token"] = self._token_generator()
            relation.data[self._app]["remote-store-insecure"] = str(self._insecure).lower()

    def _is_valid_unit_address(self, address: str) -> bool:
        """Validate a unit address.

        Args:
            address: a string representing a unit address
        """
        try:
            _ = ipaddress.ip_address(address)
            return True
        except ValueError:
            return False


class StoreEndpointsChangedEvent(ops.EventBase):
    """Event emitted when Parca store endpoints change."""

    def __init__(
        self,
        handle,
        relation_id,
        remote_store_address,
        remote_store_bearer_token,
        remote_store_insecure,
    ):
        super().__init__(handle)
        self.relation_id = relation_id
        self.store_config = {
            "remote-store-address": remote_store_address,
            "remote-store-bearer-token": remote_store_bearer_token,
            "remote-store-insecure": remote_store_insecure,
        }

    def snapshot(self):
        """Save store relation information."""
        return {"relation_id": self.relation_id, "store_config": json.dumps(self.store_config)}

    def restore(self, snapshot):
        """Restore store relation information."""
        self.relation_id = snapshot["relation_id"]
        self.store_config = json.loads(snapshot["store_config"])


class RemoveStoreEvent(ops.EventBase):
    """Event emitted when Parca store config should be removed."""

    def __init__(self, handle, relation_id):
        super().__init__(handle)
        self.relation_id = relation_id

    def snapshot(self):
        """Save store relation information."""
        return {"relation_id": self.relation_id}

    def restore(self, snapshot):
        """Restore store relation information."""
        self.relation_id = snapshot["relation_id"]


class ParcaStoreEvents(ops.ObjectEvents):
    """Event descriptor for events raised by `ParcaStoreEndpointRequirer`."""

    endpoints_changed = ops.EventSource(StoreEndpointsChangedEvent)
    remove_store = ops.EventSource(RemoveStoreEvent)


class ParcaStoreEndpointRequirer(ops.Object):
    """Provide an interface for apps that need to send data to a Parca Store."""

    on = ParcaStoreEvents()

    def __init__(self, charm, relation_name: str = DEFAULT_RELATION_NAME):
        """Construct a Parca profile store requirer.

        Args:
            charm: a `ops.CharmBase` object that manages this
                `ParcaStoreEndpointRequirer` object. Typically this is `self` in the instantiating
                class.
            relation_name: an optional string that denotes the name of the relation endpoint.
        """
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        events = self._charm.on[self._relation_name]
        self.framework.observe(events.relation_changed, self._on_parca_store_relation_changed)
        self.framework.observe(events.relation_departed, self._on_parca_store_relation_departed)

    def _on_parca_store_relation_changed(self, event):
        """Handle changes with related store requirers.

        Args:
            event: a `CharmEvent` in response to which the Parca store client
                must update its store configuration.
        """
        rel_id = event.relation.id
        rel_data = event.relation.data[event.relation.app]
        self.on.endpoints_changed.emit(
            relation_id=rel_id,
            remote_store_address=rel_data.get("remote-store-address", ""),
            remote_store_bearer_token=rel_data.get("remote-store-bearer-token", ""),
            remote_store_insecure=rel_data.get("remote-store-insecure", ""),
        )

    def _on_parca_store_relation_departed(self, event):
        """Notify requirers that the store config they received should be removed.

        Args:
            event: a `CharmEvent` in response to which the Parca store client
                must disregard its store configuration
        """
        rel_id = event.relation.id
        self.on.remove_store.emit(relation_id=rel_id)

    @property
    def config(self) -> dict:
        """Return the store config for a given requirer if the relation is formed."""
        if relation := self._charm.model.get_relation(self._relation_name):
            keys = ["remote-store-address", "remote-store-bearer-token", "remote-store-insecure"]
            return {k: relation.data[relation.app].get(k, "") for k in keys}
        else:
            return {}
