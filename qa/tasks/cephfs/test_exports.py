import logging
import random
import time
from tasks.cephfs.fuse_mount import FuseMount
from tasks.cephfs.cephfs_test_case import CephFSTestCase
from teuthology.orchestra.run import CommandFailedError

log = logging.getLogger(__name__)
class TestKillPoints(CephFSTestCase):
    # Two active MDS
    MDSS_REQUIRED = 4

    init = False

    def _setup_cluster(self):
        # Set Multi-MDS cluster
        self.fs.set_max_mds(2)

        self.fs.wait_for_daemons()
        
        # Create test data
        if self.init is False:
            self._populate_data(8)
            self.init = True

        return True

    def _populate_data(self, nfiles):
            size_mb = 8
            dname = "abc"
            self.mount_a.run_shell(["mkdir", dname])
            for i in range(nfiles):
                fname = dname + "/" + (str(i)) + ".txt"
                self.mount_a.write_n_mb(fname, size_mb)

            # Get the list of file to confirm the count of files
            self.org_files = self.mount_a.ls()

    def _verify_data(self):
        s1 = set(self.mount_a.ls())
        s2 = set(self.org_files)

        if s1.isdisjoint(s2):
            log.info("Directory contents org: %s" %str(self.org_files))
            log.info("Directory contents new: %s" %str(self.mount_a.ls()))
            return False

        log.info("Directory contents matches")
        return True

    def _run_export_dir(self, importv, exportv):

        status = self.fs.status()

        rank_0 = self.fs.get_rank(status=status, rank = 0)
        rank_1 = self.fs.get_rank(status=status, rank = 1)
        rank_0_name = rank_0['name']
        rank_1_name = rank_1['name']

        killpoint = {}
        killpoint[0] = ('export', exportv)
        killpoint[1] = ('import', importv)

        command = ["config", "set", "mds_kill_export_at", str(exportv)]
        result = self.fs.rank_asok(command, rank=0, status=status)
        assert(result["success"])

        command = ["config", "set", "mds_kill_import_at", str(importv)]
        result = self.fs.rank_asok(command, rank=1, status=status)
        assert(result["success"])

        # This should kill either or both MDS process
        try:
            # This should kill either or both MDS process
            self.mount_a.setfattr("abc", "ceph.dir.pin", "1")
        except Exception as e:
            log.error(e.__str__())

        time.sleep(150)
        status2 = self.fs.status()

        self._wait_subtrees([('/abc', 1)], status2, 1)

        #status2 = self.fs.status()

        rank_0_new = self.fs.get_rank(status=status2, rank = 0)
        rank_1_new = self.fs.get_rank(status=status2, rank = 1)
        rank_0_new_name = rank_0_new['name']
        rank_1_new_name = rank_1_new['name']

        if status2.hadfailover_rank(self.fs.id, status, 0):
            log.info("MDS %s crashed and active as MDS %s at type %s killpoint %d"
                    %(rank_0_name, rank_0_new_name, killpoint[0][0], killpoint[0][1]))

        if status2.hadfailover_rank(self.fs.id, status, 1):
            log.info("MDS %s crashed and active as MDS %s at type %s killpoint %d"
                    %(rank_1_name, rank_1_new_name, killpoint[1][0], killpoint[1][1]))

        active_mds = self.fs.get_active_names()
        if len(active_mds) != 2:
            "One or more MDS did not come up"
            return False

        log.info("logging subtrees in rank 1")
        log.info(self._get_subtrees(status=self.fs.status(), rank=1))
        if not self._verify_data():
            return False;

        #self.mount_a.run_shell(["rm -rf", "abc"])
        return True


    def _run_export(self, importv, exportv):
        if not(self._run_export_dir(importv, exportv)):
            log.error("Error for killpoint %d:%d" %(importv, exportv))
        else:
            return True

def make_test_killpoints(importv, exportv):
    def test_export_killpoints(self):
        self.init = False
        self._setup_cluster()
        assert(self._run_export(importv, exportv))
        log.info("Test passed for killpoint (%d, %d)" %(importv, exportv))
    return test_export_killpoints

for import_killpoint in range(0, 11):
    for export_killpoint in range(2, 14):
        test_export_killpoints = make_test_killpoints(import_killpoint, export_killpoint)
        setattr(TestKillPoints, "test_export_killpoints_%d_%d" % (import_killpoint, export_killpoint), test_export_killpoints)
