"""Bridge from the web layer to truestill-core. Imports only truestill-core -- never truestill-cli.

Read helpers return plain dicts for JSON; long operations return :data:`JobTarget`s that the
job manager runs on a thread with progress + cancellation. Preview writes nothing (the CLI's
dry-run posture, preserved in the UI).

This package is the F10 facade: surface modules live beside this file; symbols are re-exported
here so ``from truestill_app.service import …`` and ``service.…`` stay unchanged.
"""

from __future__ import annotations

from truestill_app.service import backup as _backup
from truestill_app.service import bake as _bake
from truestill_app.service import clean_empty as _clean_empty
from truestill_app.service import drive_support as _drive_support
from truestill_app.service import drives as _drives
from truestill_app.service import fs_browse as _fs_browse
from truestill_app.service import leftover_cleanup as _leftover_cleanup
from truestill_app.service import media_support as _media_support
from truestill_app.service import migrate as _migrate
from truestill_app.service import organize as _organize
from truestill_app.service import organize_undo as _organize_undo
from truestill_app.service import settings as _settings
from truestill_app.service import stats as _stats
from truestill_app.service import takeout as _takeout
from truestill_app.service import trips as _trips
from truestill_app.service import verify as _verify

# --- fs_browse ---
FsRoot = _fs_browse.FsRoot
FsEntry = _fs_browse.FsEntry
FsDirsOk = _fs_browse.FsDirsOk
FsDirsErr = _fs_browse.FsDirsErr
FsValidateResolved = _fs_browse.FsValidateResolved
FsValidateUnresolved = _fs_browse.FsValidateUnresolved
FsCreateFailed = _fs_browse.FsCreateFailed
FsCreateOk = _fs_browse.FsCreateOk
fs_roots = _fs_browse.fs_roots
fs_dirs = _fs_browse.fs_dirs
fs_create = _fs_browse.fs_create
fs_validate = _fs_browse.fs_validate

# --- clean_empty ---
CleanEmptyOccupied = _clean_empty.CleanEmptyOccupied
CleanEmptyPreview = _clean_empty.CleanEmptyPreview
CleanEmptyApply = _clean_empty.CleanEmptyApply
clean_empty_preview = _clean_empty.clean_empty_preview
clean_empty_apply = _clean_empty.clean_empty_apply

# --- organize_undo ---
OrganizeUndoSkipped = _organize_undo.OrganizeUndoSkipped
OrganizeUndoStateDisarmed = _organize_undo.OrganizeUndoStateDisarmed
OrganizeUndoStateArmed = _organize_undo.OrganizeUndoStateArmed
OrganizeUndoJobSummary = _organize_undo.OrganizeUndoJobSummary
organize_undo_state = _organize_undo.organize_undo_state
organize_undo = _organize_undo.organize_undo

# --- settings ---
EventSettingsPayload = _settings.EventSettingsPayload
InvalidEventSettingsPayload = _settings.InvalidEventSettingsPayload
event_settings = _settings.event_settings
event_settings_payload = _settings.event_settings_payload
invalid_event_settings_payload = _settings.invalid_event_settings_payload
set_event_settings = _settings.set_event_settings
EverydayDaySettingsPayload = _settings.EverydayDaySettingsPayload
InvalidEverydayDaySettingsPayload = _settings.InvalidEverydayDaySettingsPayload
everyday_day_settings = _settings.everyday_day_settings
everyday_day_settings_payload = _settings.everyday_day_settings_payload
invalid_everyday_day_settings_payload = _settings.invalid_everyday_day_settings_payload
set_everyday_day_settings = _settings.set_everyday_day_settings
LayoutPreviewRow = _settings.LayoutPreviewRow
LayoutState = _settings.LayoutState
PreviewLayoutOk = _settings.PreviewLayoutOk
PreviewLayoutErr = _settings.PreviewLayoutErr
SetLayoutOk = _settings.SetLayoutOk
SetLayoutErr = _settings.SetLayoutErr
layout_state = _settings.layout_state
preview_layout = _settings.preview_layout
set_layout = _settings.set_layout

# --- takeout ---
InferredLocalShiftPayload = _takeout.InferredLocalShiftPayload
IngestPreviewEmpty = _takeout.IngestPreviewEmpty
IngestPreviewSummary = _takeout.IngestPreviewSummary
ingest_preview = _takeout.ingest_preview
ingest_preview_run = _takeout.ingest_preview_run

# --- drive_support ---
NotABackupDriveError = _drive_support.NotABackupDriveError
DriveCorrectionPayload = _drive_support.DriveCorrectionPayload
DriveUnavailablePayload = _drive_support.DriveUnavailablePayload
not_a_drive_message = _drive_support.not_a_drive_message
drive_correction = _drive_support.drive_correction
drive_unavailable = _drive_support.drive_unavailable
drive_ref_for = _drive_support.drive_ref_for
not_a_drive = _drive_support.not_a_drive
drive_path_hint = _drive_support.drive_path_hint
take_live_path_hint = _drive_support.take_live_path_hint
_not_a_drive_message = _drive_support.not_a_drive_message
_drive_correction = _drive_support.drive_correction
_drive_unavailable = _drive_support.drive_unavailable
_not_a_drive = _drive_support.not_a_drive
_drive_path_hint = _drive_support.drive_path_hint
_take_live_path_hint = _drive_support.take_live_path_hint

# --- media_support ---
MediaBreakdown = _media_support.MediaBreakdown
media_breakdown = _media_support.media_breakdown
_media_breakdown = _media_support.media_breakdown

# --- stats ---
LibraryStatsDrive = _stats.LibraryStatsDrive
LibraryStatsSafety = _stats.LibraryStatsSafety
LibraryStatsUndatedSample = _stats.LibraryStatsUndatedSample
LibraryStatsCompleteness = _stats.LibraryStatsCompleteness
LibraryStatsYear = _stats.LibraryStatsYear
LibraryStatsShape = _stats.LibraryStatsShape
LibraryStats = _stats.LibraryStats
library_stats = _stats.library_stats

# --- verify ---
VerifyProblem = _verify.VerifyProblem
VerifyJobSummary = _verify.VerifyJobSummary
verify_run = _verify.verify_run

# --- drives ---
LIBRARY_PATH_HINT = _drives.LIBRARY_PATH_HINT
BACKUP_PATH_HINT = _drives.BACKUP_PATH_HINT
RevealOk = _drives.RevealOk
RevealErr = _drives.RevealErr
reveal_in_file_manager = _drives.reveal_in_file_manager
DriveAttachment = _drives.DriveAttachment
attach_drive = _drives.attach_drive
bake_preview = _bake.bake_preview
bake_run = _bake.bake_run
DriveRow = _drives.DriveRow
WhereCopy = _drives.WhereCopy
WhereResult = _drives.WhereResult
AtRiskRow = _drives.AtRiskRow
list_drives = _drives.list_drives
where = _drives.where
at_risk = _drives.at_risk
LibraryStatus = _drives.LibraryStatus
library_status = _drives.library_status

# --- backup ---
MissingCopy = _backup.MissingCopy
BackupPreviewErr = _backup.BackupPreviewErr
BackupPreviewOk = _backup.BackupPreviewOk
backup_preview = _backup.backup_preview
BackupRunSummary = _backup.BackupRunSummary
backup_run = _backup.backup_run
_files_missing_on_target = _backup._files_missing_on_target

# --- leftover_cleanup ---
LeftoverEmptyFolders = _leftover_cleanup.LeftoverEmptyFolders
cleanup_summary_from_results = _leftover_cleanup.cleanup_summary_from_results
cleanup_summary_from_old_paths = _leftover_cleanup.cleanup_summary_from_old_paths
_cleanup_summary_from_results = _leftover_cleanup.cleanup_summary_from_results
_cleanup_summary_from_old_paths = _leftover_cleanup.cleanup_summary_from_old_paths

# --- organize ---
ORGANIZE_MODE_KEY = _organize.ORGANIZE_MODE_KEY
ORGANIZE_MODES = _organize.ORGANIZE_MODES
SIDEBAR_COLLAPSED_KEY = _organize.SIDEBAR_COLLAPSED_KEY
OrganizeDedupCore = _organize.OrganizeDedupCore
OrganizeInventory = _organize.OrganizeInventory
organize_inventory = _organize.organize_inventory
OrganizeModeState = _organize.OrganizeModeState
SetOrganizeModeResult = _organize.SetOrganizeModeResult
SidebarState = _organize.SidebarState
SetSidebarCollapsedResult = _organize.SetSidebarCollapsedResult
organize_mode_state = _organize.organize_mode_state
set_organize_mode = _organize.set_organize_mode
sidebar_state = _organize.sidebar_state
set_sidebar_collapsed = _organize.set_sidebar_collapsed
FilesystemRelationshipOk = _organize.FilesystemRelationshipOk
FilesystemRelationshipErr = _organize.FilesystemRelationshipErr
filesystem_relationship = _organize.filesystem_relationship
ModeMechanism = _organize.ModeMechanism
OrganizePreviewEmpty = _organize.OrganizePreviewEmpty
OrganizePreviewSummary = _organize.OrganizePreviewSummary
organize_preview = _organize.organize_preview
organize_preview_run = _organize.organize_preview_run
organize_run = _organize.organize_run
CompletionBase = _organize.CompletionBase
OrganizeDoneSummary = _organize.OrganizeDoneSummary
_summarize = _organize._summarize
_skipped_summary = _organize._skipped_summary

# --- trips ---
EventProposalDriveErrorPayload = _trips.EventProposalDriveErrorPayload
plan_resolve = _trips.plan_resolve
ReviewDayPayload = _trips.ReviewDayPayload
ReviewCardPayload = _trips.ReviewCardPayload
CollapsedEventSummaryPayload = _trips.CollapsedEventSummaryPayload
ReviewCardsPayload = _trips.ReviewCardsPayload
ProposedReviewCardsPayload = _trips.ProposedReviewCardsPayload
review_card_json = _trips.review_card_json
collapsed_event_summary = _trips.collapsed_event_summary
review_cards_payload = _trips.review_cards_payload
proposed_review_cards_payload = _trips.proposed_review_cards_payload
InvalidEventProposalPayload = _trips.InvalidEventProposalPayload
EventProposalSuccessPayload = _trips.EventProposalSuccessPayload
invalid_event_proposal_payload = _trips.invalid_event_proposal_payload
propose_events = _trips.propose_events
MergeReviewCardsResult = _trips.MergeReviewCardsResult
merge_event_review_cards = _trips.merge_event_review_cards
split_event_review_card = _trips.split_event_review_card
NamedEventSelection = _trips.NamedEventSelection
NamedTripSelection = _trips.NamedTripSelection
ApplyReviewNamesResult = _trips.ApplyReviewNamesResult
apply_event_review_names = _trips.apply_event_review_names

# --- migrate ---
MigrationMove = _migrate.MigrationMove
MigrationPreviewOk = _migrate.MigrationPreviewOk
migration_preview = _migrate.migration_preview
migration_preview_run = _migrate.migration_preview_run
AppliedReviewGroupPayload = _migrate.AppliedReviewGroupPayload
MigrationApplySummary = _migrate.MigrationApplySummary
migration_apply = _migrate.migration_apply
ArmedStatePayload = _migrate.ArmedStatePayload
UndoRefusalPayload = _migrate.UndoRefusalPayload
UndoJobSummary = _migrate.UndoJobSummary
migration_armed_state = _migrate.migration_armed_state
migration_undo = _migrate.migration_undo
_reveal_folder_on_drive = _migrate._reveal_folder_on_drive
