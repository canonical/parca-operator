# Parca Operator for Juju Controllers

**NOTE: This operator is not production ready, and should be used for testing purposes only!**

This charm is the result of an afternoon of experimentation with Parca, published here as a memory
jogger for future me!

It represents a simple deployment of the Parca server, along with configuration to run
`juju-introspect` as a systemd service to allow Parca to scrape profiling information from the
machine agent.

This operator will install the latest Parca release from Github, and install it along with the
relevant systemd units to start it and configure it.

## Usage

This operator has been tested profiling machine based Juju controllers (as opposed to Kubernetes
controllers!)

You can deploy the operator as such:

```shell
# Bootstrap a new Juju controller on LXD
$ juju bootstrap localhost lxd
# Switch to the controller model
$ juju switch controller
# Deploy the charm to the controller machine
$ juju deploy parca-juju-profiler --to 0
```

Once the deployment is complete, you can get to the Parca dashboard at:
`http://<controller-address>:7070/`

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
