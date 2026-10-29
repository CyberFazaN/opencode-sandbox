"""C08 and D11. C08: a first start whose `docker run` fails because the published host port
is taken leaves no container, and `config apply` fixes the port directly. D11: two
default snapshots in one second get two tags. The port is held by a socket of this
test process on 127.0.0.1 only."""
import socket


def test_failed_first_start_then_config_apply(campaign, checks):
    camp, ck = campaign, checks
    name = "ocs-test-port-taken"
    eid = camp.create(name, "--no-integrations")
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        camp.ocs("config", "apply", name, "--publish", f"{port}:8080", "--yes")
        failed = camp.ocs("start", name, check=False)
        left = camp.docker("container", "ls", "-a", "--filter", f"name=^ocs-{eid}$", "--format", "{{.Status}}").stdout.strip()
        meta = camp.metadata(name)
        ck(failed.returncode != 0 and meta["status"] == "error", f"C08 start fails with the port taken ({meta['status']})")
        ck(left == "", f"C08 no container left after the failed docker run ({left!r})")
    finally:
        holder.close()
    applied = camp.ocs("config", "apply", name, "--no-ports", "--yes", check=False)
    ck(applied.returncode == 0, f"C08 config apply fixes the port without repair ({applied.stdout.strip()[-200:]})")
    camp.ocs("start", name)
    ck(camp.inspect(eid)["State"]["Running"], "C08 start works afterwards")

    # D11 two default snapshots in one second
    camp.ocs("stop", name)
    first = camp.ocs("container", "snapshot", name).stdout.strip().splitlines()[-1]
    second = camp.ocs("container", "snapshot", name).stdout.strip().splitlines()[-1]
    camp.note(f"images {first} {second} (snapshots of {name})")
    present = [camp.docker("image", "inspect", t, check=False).returncode == 0 for t in (first, second)]
    ck(first != second and all(present) and first.startswith(f"ocs-snapshot:{eid}-"),
       f"D11 two snapshots, two tags, both present ({first}, {second})")
    camp.delete(name)
    for tag in (first, second):
        camp.docker("image", "rm", tag, check=False)
    camp.note("removed the two snapshot tags")
