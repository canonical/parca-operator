# Parca Operator

Parca provides continuous profiling for analysis of CPU and memory usage, down to the line number
and throughout time. Saving infrastructure cost, improving performance, and increasing reliability.

This operator builds a simple deployment of the Parca server and provides a relation interface such
that it can be integrated with other Juju charms in a model. A good example of this is the
[juju-introspect](https://charmhub.io/juju-introspect) operator, which when related to this charm
will enable continuous profiling of the Juju controller its attached to.

## Usage

You can deploy the operator as such:

```shell
# Deploy the charm
$ juju deploy parca --channel edge
```

Once the deployment is complete, grab the address of the Parca application:

```bash
$ juju show-unit parca/0 --format=json | jq -r '.["parca/0"]["public-address"]'
```

Now visit: `http://<parca-address>:7070/` to see the Parca dashboard.

## Profiling a Juju Controller

You can deploy this charm alongside `juju-introspect` to profile a running controller like so:

```shell
# Bootstrap a new Juju controller on LXD
$ juju bootstrap localhost lxd

# Switch to the controller model
$ juju switch controller

# Deploy the juju-introspect charm to the controller machine
$ juju deploy --to=0 juju-introspect --channel edge

# Deploy the Parca charm
$ juju deploy parca --channel edge

# Relate the two charms to enable scraping
$ juju relate parca juju-introspect
```

If you visit the Parca dashboard, you should now see profiles for the related Juju controller.

## Configuration

By default, Parca will store profiles **in memory**. This is the current default, as the
persistence settings are very new and prone to breaking! The default limit for in-memory storage is
4096MB. When Parca reaches that limit, profiles are purged.

The in-memory storage limit is configurable like so:

```bash
# Increase limit to 8192MB
$ juju config parca memory-storage-limit=8192
```

If you wish to enable the **experimental** storage persistence, you can do as such:

```bash
$ juju config parca storage-persist=true
```
