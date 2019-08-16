======
LazyIO
======

LazyIO relaxes POSIX semantics. Buffered reads/writes are allowed even when a
file is opened by multiple applications on multiple clients. Applications are
responsible for managing cache coherency themselves.

Libcephfs supports LazyIO since nautilus release.

Enable LazyIO
=============

LazyIO can be enabled by following ways.

- ``client_force_lazyio`` option enables LAZY_IO globally for libcephfs and
  ceph-fuse mount.

- ``ceph_lazyio(...)`` and ``ceph_ll_lazyio(...)`` enable LAZY_IO for file handle
  in libcephfs.

- ``ioctl(fd, CEPH_IOC_LAZYIO, 1UL)`` enables LAZY_IO for file handle in
   ceph-fuse mount.

 Using LazyIO
 ============

 LazyIO includes two two methods ``lazyio_propagate()`` and ``lazyio_synchronize()``. With LazyIO enabled, writes may not be visble to other clients until ``lazyio_propagate()`` is called. Reads may come from local cache (irrespective of changes to the file by other clients) until ``lazyio_synchronize()`` is called.

- ``lazyio_propagate(...)`` - Ensures that any buffered writes of the calling client, in the specific region, has been propagated to the shared file.

- ``lazyio_synchronize(...)`` - Ensures that the calling client is, in a subsequent read call, able to read the updated file with all the propagated writes of the other clients. In CephFS this is facilitated by invalidating the inode of the file and hence forces the client to refetch/recache the data from the updated file. Also if the write cache of the calling client is dirty(not propagated), lazyio_synchronize() flushes it as well.

An example usage(utilizing libcephfs) would be:

::

        /* ca and cb open the shared file file.txt */
        int fda = ceph_open(ca, "file.txt", O_CREAT|O_RDWR, 0644); 
        int fdb = ceph_open(ca, "file.txt", O_CREAT|O_RDWR, 0644);

        /* Enable LazyIO on both clients */
        ceph_lazyio(ca, fda, 1));
        ceph_lazyio(cb, fdb, 1));

        char out_buf[] = "fooooooooo";
        
        /* ca and cb issue a write and propagates it respectively */
        ceph_write(ca, fda, out_buf, sizeof(out_buf), 0);*/
        ceph_propagate(ca, fda, 0, 0);

        ceph_write(cb, fdb, out_buf, sizeof(out_buf), 10));
        ceph_lazyio_propagate(cb, fdb, 0, 0);

        char in_buf[40];
        /* Calling ceph_lazyio_synchronize here will enable ca to fetch the propagated writes of cb in the subsequent read */
        ceph_lazyio_synchronize(ca, fda, 0, 0);
        ceph_read(ca, fda, in_buf, sizeof(in_buf), 0);
        
        /* cb does not need to call ceph_lazyio_synchronize here because it is the latest writer and the writes before it have already been propagated*/
        ceph_read(cb, fdb, in_buf, sizeof(in_buf), 0);
  
In the above example, ca and cb both read "fooooooooofooooooooo".




 
