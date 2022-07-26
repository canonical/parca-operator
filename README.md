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

Once the deployment is complete, you can get to the Parca dashboard at:
`http://<controller-address>:7070/`

To profile a Juju controller, you can do the following:

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

## Configuration

By default, Parca will store profiles **in memory**. This is the current default, as the
persistence settings are very new and prone to breaking! The default limit for in-memory storage is
4096MB. When Parca reaches that limit, profiles are purged.

The in-memory storage limit is configurable like so:

```bash
# Increase limit to 8192MB
$ juju config parca-juju-profiler memory-storage-limit=8192
```

If you wish to enable the **experimental** storage persistence, you can do as such:

```bash
$ juju config parca-juju-profiler storage-persist=true
```
