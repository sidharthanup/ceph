import logging
import errno
from tasks.cephfs.cephfs_test_case import CephFSTestCase
from teuthology.orchestra.run import CommandFailedError

log = logging.getLogger(__name__)

class TestScrub2(CephFSTestCase):
    MDSS_REQUIRED = 3
    CLIENTS_REQUIRED = 1

    def _get_scrub_status(self):
        return self.fs.rank_tell(["scrub", "status"], 0)

    def _wait_until_scrubbed(self, timeout):
        self.wait_until_true(lambda: "no active" in self._get_scrub_status()['status'], timeout)

    def _find_path_inos(self, root_path):
        inos = []
        p = self.mount_a.run_shell(["find", root_path])
        paths = p.stdout.getvalue().strip().split()
        for path in paths:
            inos.append(self.mount_a.path_to_ino(path))
        return inos

    def _setup_subtrees(self):
        self.fs.set_max_mds(3)
        self.fs.wait_for_daemons()
        status = self.fs.status()

        path = 'd1/d2/d3/d4/d5/d6/d7/d8'
        self.mount_a.run_shell(['mkdir', '-p', path])
        self.mount_a.run_shell(['sync', path])

        self.mount_a.setfattr("d1/d2", "ceph.dir.pin", "1")
        self.mount_a.setfattr("d1/d2/d3/d4", "ceph.dir.pin", "2")
        self.mount_a.setfattr("d1/d2/d3/d4/d5/d6", "ceph.dir.pin", "0")
        self._wait_subtrees([('/d1/d2', 1), ('/d1/d2/d3/d4', 2), ('/d1/d2/d3/d4/d5/d6', 0)], status=status, rank=0)

        for rank in range(3):
            self.fs.rank_tell(["flush", "journal"], rank)

    def test_apply_tag(self):
        self._setup_subtrees()
        inos = self._find_path_inos('d1/d2/d3/')

        tag = "tag123"
        self.fs.rank_tell(["tag", "path", "/d1/d2/d3", tag], 0)
        self._wait_until_scrubbed(30);

        def assertTagged(ino):
            file_obj_name = "{0:x}.00000000".format(ino)
            self.fs.rados(["getxattr", file_obj_name, "scrub_tag"])

        for ino in inos:
            assertTagged(ino)

    def test_scrub_backtrace(self):
        self._setup_subtrees()
        inos = self._find_path_inos('d1/d2/d3/')

        for ino in inos:
            file_obj_name = "{0:x}.00000000".format(ino)
            self.fs.rados(["rmxattr", file_obj_name, "parent"])

        self.fs.rank_tell(["scrub", "start", "/d1/d2/d3", "recursive", "force"], 0)
        self._wait_until_scrubbed(30);

        def _check_damage(mds_rank, inos):
            all_damage = self.fs.rank_tell(["damage", "ls"], mds_rank)
            damage = [d for d in all_damage if d['ino'] in inos and d['damage_type'] == "backtrace"]
            return len(damage) >= len(inos)

        self.assertTrue(_check_damage(1, inos[0:2]))
        self.assertTrue(_check_damage(2, inos[2:4]))
        self.assertTrue(_check_damage(0, inos[4:6]))

    def test_scrub_non_mds0(self):
        self._setup_subtrees()

        def expect_exdev(cmd, mds):
            try:
                self.fs.mon_manager.raw_cluster_cmd('tell', 'mds.{0}'.format(mds), *cmd)
            except CommandFailedError as e:
                if e.exitstatus == errno.EXDEV:
                    pass
                else:
                    raise
            else:
                raise RuntimeError("expected failure")

        rank1 = self.fs.get_rank(rank=1)
        expect_exdev(["scrub", "start", "/d1/d2/d3"], rank1["name"])
        expect_exdev(["scrub", "abort"], rank1["name"])
        expect_exdev(["scrub", "pause"], rank1["name"])
        expect_exdev(["scrub", "resume"], rank1["name"])
