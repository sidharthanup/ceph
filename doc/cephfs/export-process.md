========================================
Export Process During Subtree Migrations
========================================

Once the exporter verifies that the subtree is permissible to be exported
(Non degraded cluster, non-frozen subtree root), the subtree root
directory is temporarily auth pinned, the subtree freeze is initiated,
and the exporter is committed to the subtree migration, barring an
intervening failure of the importer or itself.

The MExportDiscover message is exchanged to ensure that the inode for the
base directory being exported is open on the destination node. It is
auth pinned by the importer to prevent it from being trimmed.  This occurs
before the exporter completes the freeze of the subtree to ensure that
the importer is able to replicate the necessary metadata.  When the
exporter receives the MDiscoverAck, it allows the freeze to proceed by
removing its temporary auth pin.

A warning stage occurs only if the base subtree directory is open by
nodes other than the importer and exporter.  If it is not, then this
implies that no metadata within or nested beneath the subtree is
replicated by any node other than the importer an exporter.  If it is,
then a MExportWarning message informs any bystanders that the
authority for the region is temporarily ambiguous, and lists both the
exporter and importer as authoritative MDS nodes.  In particular,
bystanders who are trimming items from their cache must send
MCacheExpire messages to both the old and new authorities.  This is
necessary to ensure that the surviving authority reliably receives all
expirations even if the importer or exporter fails.  While the subtree
is frozen (on both the importer and exporter), expirations will not be
immediately processed; instead, they will be queued until the region
is unfrozen and it can be determined that the node is or is not
authoritative.

The exporter then packages an MExport message containing all metadata
of the subtree and flags the objects as non-authoritative. The MExport message sends
the actual subtree metadata to the importer.  Upon receipt, the
importer inserts the data into its cache, marks all objects as
authoritative, and logs a copy of all metadata in an EImportStart
journal message.  Once that has safely flushed, it replies with an
MExportAck.  The exporter can now log an EExport journal entry, which
ultimately specifies that the export was a success.  In the presence
of failures, it is the existence of the EExport entry only that
disambiguates authority during recovery.

Once logged, the exporter will send an MExportNotify to any
bystanders, informing them that the authority is no longer ambiguous
and cache expirations should be sent only to the new authority (the
importer).  Once these are acknowledged back to the exporter,
implicitly flushing the bystander to exporter message streams of any
stray expiration notices, the exporter unfreezes the subtree, cleans
up its migration-related state, and sends a final MExportFinish to the
importer.  Upon receipt, the importer logs an EImportFinish(true)
(noting locally that the export was indeed a success), unfreezes its
subtree, processes any queued cache expierations, and cleans up its
state.
