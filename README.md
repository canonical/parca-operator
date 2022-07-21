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
