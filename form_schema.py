SYSTEM_TYPE_OPTIONS = [
    ("", "Select system type"),
    ("64-bit", "64-bit"),
    ("32-bit", "32-bit"),
]

STATUS_OPTIONS = [
    ("", "Select status"),
    ("Resolved", "Resolved"),
    ("Pending", "Pending"),
]

FIELD_SECTIONS = [
    {
        "title": "Practical Header",
        "description": "Basic information from the Windows Computer Clean-Up and Virtual Memory Practical.",
        "fields": [
            {
                "name": "department",
                "label": "Department",
                "type": "text",
                "default": "ICT Department",
                "required": True,
            },
            {
                "name": "practical_title",
                "label": "Practical Title",
                "type": "text",
                "default": "Windows Update, Cache Cleaning, Temporary File Removal and Virtual Memory Configuration",
                "required": True,
                "full_width": True,
            },
            {"name": "intern_name", "label": "Student/Intern Name", "type": "text", "required": True},
            {"name": "computer_name", "label": "Computer Name", "type": "text", "required": True},
            {"name": "office_department", "label": "Department/Office", "type": "text"},
            {"name": "practical_date", "label": "Date", "type": "date", "required": True},
            {"name": "supervisor", "label": "Supervisor", "type": "text", "required": True},
        ],
    },
    {
        "title": "Part A: Computer Information",
        "description": "Record details from msinfo32.",
        "fields": [
            {"name": "recorded_computer_name", "label": "Computer Name", "type": "text"},
            {"name": "windows_version", "label": "Windows Version", "type": "text"},
            {"name": "system_manufacturer", "label": "System Manufacturer", "type": "text"},
            {"name": "system_model", "label": "System Model", "type": "text"},
            {"name": "installed_physical_ram", "label": "Installed Physical RAM", "type": "text"},
            {"name": "processor", "label": "Processor", "type": "text"},
            {
                "name": "system_type",
                "label": "System Type",
                "type": "select",
                "options": SYSTEM_TYPE_OPTIONS,
            },
            {
                "name": "computer_info_recorded",
                "label": "Computer information recorded successfully",
                "type": "checkbox",
            },
            {
                "name": "computer_info_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part B: Available Storage",
        "description": "Record Local Disk (C:) storage before cleanup.",
        "fields": [
            {
                "name": "total_disk_size_gb",
                "label": "Total disk size (GB)",
                "type": "number",
                "step": "0.01",
            },
            {
                "name": "free_space_before_gb",
                "label": "Free space before cleanup (GB)",
                "type": "number",
                "step": "0.01",
            },
            {
                "name": "used_space_before_gb",
                "label": "Used space before cleanup (GB)",
                "type": "number",
                "step": "0.01",
            },
            {
                "name": "available_disk_checked",
                "label": "Available disk space checked and recorded",
                "type": "checkbox",
            },
            {
                "name": "powershell_admin_opened",
                "label": "PowerShell opened as administrator",
                "type": "checkbox",
            },
            {
                "name": "disk_space_command_executed",
                "label": "Get-PSDrive command executed successfully",
                "type": "checkbox",
            },
            {
                "name": "disk_space_information_recorded",
                "label": "Disk space information recorded",
                "type": "checkbox",
            },
            {
                "name": "disk_space_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part C: System Restore Point",
        "description": "Confirm system protection and record the restore point.",
        "fields": [
            {
                "name": "system_protection_enabled",
                "label": "System Protection was enabled",
                "type": "checkbox",
            },
            {
                "name": "restore_point_created",
                "label": "Restore point was created successfully",
                "type": "checkbox",
            },
            {
                "name": "restore_point_name",
                "label": "Restore point name",
                "type": "text",
                "default": "Before ICT Cleanup",
            },
            {
                "name": "restore_point_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part D: User Temporary Files",
        "description": "Track manual and PowerShell cleanup of the current user's temporary files.",
        "fields": [
            {"name": "user_temp_opened", "label": "%temp% folder opened successfully", "type": "checkbox"},
            {"name": "user_temp_selected", "label": "Temporary files selected", "type": "checkbox"},
            {"name": "user_temp_deleted", "label": "Temporary files deleted", "type": "checkbox"},
            {"name": "user_temp_in_use_skipped", "label": "Files currently in use were skipped", "type": "checkbox"},
            {"name": "user_temp_ps_executed", "label": "PowerShell command executed", "type": "checkbox"},
            {"name": "user_temp_ps_cleared", "label": "User temporary files were cleared", "type": "checkbox"},
            {
                "name": "user_temp_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part E: Windows Temporary Files",
        "description": "Track manual and PowerShell cleanup of C:\\Windows\\Temp.",
        "fields": [
            {"name": "windows_temp_opened", "label": "Windows temporary folder opened", "type": "checkbox"},
            {
                "name": "windows_temp_deleted",
                "label": "Unnecessary Windows temporary files deleted",
                "type": "checkbox",
            },
            {"name": "windows_temp_in_use_skipped", "label": "Files in use were skipped", "type": "checkbox"},
            {"name": "windows_temp_ps_executed", "label": "PowerShell command executed", "type": "checkbox"},
            {"name": "windows_temp_ps_cleared", "label": "Windows temporary files cleared", "type": "checkbox"},
            {
                "name": "windows_temp_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part F: Recycle Bin",
        "description": "Record manual and PowerShell Recycle Bin cleanup.",
        "fields": [
            {"name": "recycle_bin_emptied", "label": "Recycle Bin emptied successfully", "type": "checkbox"},
            {"name": "recycle_bin_ps_executed", "label": "PowerShell command executed", "type": "checkbox"},
            {"name": "recycle_bin_ps_cleared", "label": "Recycle Bin cleared", "type": "checkbox"},
            {
                "name": "recycle_bin_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part G: DNS Cache",
        "description": "Record the ipconfig /flushdns result.",
        "fields": [
            {"name": "dns_cache_command_executed", "label": "DNS cache command executed", "type": "checkbox"},
            {"name": "dns_cache_success_displayed", "label": "Success message displayed", "type": "checkbox"},
            {
                "name": "dns_cache_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part H: Microsoft Store Cache",
        "description": "Record wsreset.exe completion.",
        "fields": [
            {
                "name": "store_cache_reset_executed",
                "label": "Microsoft Store cache reset command executed",
                "type": "checkbox",
            },
            {"name": "store_cache_completed", "label": "Process completed without an error", "type": "checkbox"},
            {
                "name": "store_cache_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part I: Disk Cleanup",
        "description": "Record cleanmgr selections and completion.",
        "fields": [
            {"name": "disk_cleanup_opened", "label": "Disk Cleanup opened", "type": "checkbox"},
            {
                "name": "disk_cleanup_categories_selected",
                "label": "Appropriate cleanup categories selected",
                "type": "checkbox",
            },
            {
                "name": "downloads_not_deleted_without_approval",
                "label": "Downloads folder was not deleted without approval",
                "type": "checkbox",
            },
            {"name": "disk_cleanup_completed", "label": "Disk Cleanup completed successfully", "type": "checkbox"},
            {"name": "clean_temp_internet_files", "label": "Temporary Internet Files selected", "type": "checkbox"},
            {"name": "clean_downloaded_program_files", "label": "Downloaded Program Files selected", "type": "checkbox"},
            {"name": "clean_delivery_optimization_files", "label": "Delivery Optimization Files selected", "type": "checkbox"},
            {"name": "clean_directx_shader_cache", "label": "DirectX Shader Cache selected", "type": "checkbox"},
            {"name": "clean_temporary_files", "label": "Temporary files selected", "type": "checkbox"},
            {"name": "clean_thumbnails", "label": "Thumbnails selected", "type": "checkbox"},
            {"name": "clean_windows_error_reports", "label": "Windows error reports selected", "type": "checkbox"},
            {"name": "clean_recycle_bin", "label": "Recycle Bin selected", "type": "checkbox"},
            {
                "name": "disk_cleanup_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part J: Windows Update Cache",
        "description": "Track Windows Update service stop, cache removal, and restart.",
        "fields": [
            {"name": "wuauserv_stopped", "label": "Windows Update service stopped", "type": "checkbox"},
            {"name": "bits_stopped", "label": "Background Intelligent Transfer Service stopped", "type": "checkbox"},
            {"name": "update_cache_cleared", "label": "Windows Update download cache cleared", "type": "checkbox"},
            {"name": "bits_restarted", "label": "Background Intelligent Transfer Service restarted", "type": "checkbox"},
            {"name": "wuauserv_restarted", "label": "Windows Update service restarted", "type": "checkbox"},
            {
                "name": "windows_update_cache_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part K: Repair Windows Components",
        "description": "Record DISM and System File Checker outcomes.",
        "fields": [
            {"name": "dism_operation_success", "label": "DISM operation completed successfully", "type": "checkbox"},
            {"name": "dism_corruption_repaired", "label": "DISM corruption was detected and repaired", "type": "checkbox"},
            {"name": "dism_completed_errors", "label": "DISM command completed with errors", "type": "checkbox"},
            {
                "name": "dism_result_message",
                "label": "DISM result or error message",
                "type": "textarea",
                "full_width": True,
            },
            {"name": "sfc_no_violations", "label": "SFC did not find integrity violations", "type": "checkbox"},
            {"name": "sfc_corrupt_repaired", "label": "SFC corrupt files were found and repaired", "type": "checkbox"},
            {
                "name": "sfc_corrupt_unrepaired",
                "label": "SFC corrupt files were found but some could not be repaired",
                "type": "checkbox",
            },
            {"name": "sfc_not_complete", "label": "SFC scan did not complete", "type": "checkbox"},
            {
                "name": "sfc_result_message",
                "label": "SFC result or error message",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part L: Windows Updates",
        "description": "Record update checks, installations, and restart requirement.",
        "fields": [
            {"name": "windows_update_opened", "label": "Windows Update opened", "type": "checkbox"},
            {"name": "update_check_completed", "label": "Update check completed", "type": "checkbox"},
            {"name": "security_updates_installed", "label": "Available security updates installed", "type": "checkbox"},
            {"name": "quality_updates_installed", "label": "Available quality updates installed", "type": "checkbox"},
            {
                "name": "driver_updates_reviewed",
                "label": "Driver updates reviewed by ICT supervisor",
                "type": "checkbox",
            },
            {"name": "restart_requirement_recorded", "label": "Restart requirement recorded", "type": "checkbox"},
            {
                "name": "updates_installed",
                "label": "Updates installed",
                "type": "textarea",
                "full_width": True,
            },
            {
                "name": "windows_update_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part M: Virtual Memory",
        "description": "Record automatic page-file or virtual-memory setting checks.",
        "fields": [
            {
                "name": "automatic_virtual_memory_enabled",
                "label": "Automatic virtual memory enabled",
                "type": "checkbox",
            },
            {
                "name": "pagefile_automatic_managed_confirmed",
                "label": "AutomaticManagedPagefile confirmed",
                "type": "checkbox",
            },
            {
                "name": "virtual_memory_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part N: Restart the Computer",
        "description": "Record safe restart preparation and post-restart status.",
        "fields": [
            {"name": "all_documents_saved", "label": "All documents saved", "type": "checkbox"},
            {"name": "all_programs_closed", "label": "All programs closed", "type": "checkbox"},
            {"name": "user_informed_restart", "label": "User informed about the restart", "type": "checkbox"},
            {
                "name": "windows_update_safe_stage",
                "label": "Windows Update completed or paused at a safe stage",
                "type": "checkbox",
            },
            {"name": "computer_restarted_successfully", "label": "Computer restarted successfully", "type": "checkbox"},
            {"name": "windows_started_normally", "label": "Windows started normally after restart", "type": "checkbox"},
            {"name": "user_logged_in", "label": "User successfully logged in", "type": "checkbox"},
            {
                "name": "restart_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part O: Post-Cleanup Checks",
        "description": "Record final free space and basic computer function checks.",
        "fields": [
            {
                "name": "free_space_after_gb",
                "label": "Free space after cleanup (GB)",
                "type": "number",
                "step": "0.01",
            },
            {
                "name": "space_recovered_gb",
                "label": "Space recovered (GB)",
                "type": "number",
                "step": "0.01",
            },
            {"name": "post_cleanup_disk_checked", "label": "Disk space checked after cleanup", "type": "checkbox"},
            {"name": "space_recovered_calculated", "label": "Space recovered calculated and recorded", "type": "checkbox"},
            {"name": "pagefile_setting_confirmed", "label": "Page-file setting confirmed", "type": "checkbox"},
            {"name": "computer_starts_normally", "label": "Computer starts normally", "type": "checkbox"},
            {"name": "keyboard_works", "label": "Keyboard works", "type": "checkbox"},
            {"name": "mouse_works", "label": "Mouse works", "type": "checkbox"},
            {"name": "internet_connection_works", "label": "Internet connection works", "type": "checkbox"},
            {"name": "office_apps_open", "label": "Office applications open", "type": "checkbox"},
            {"name": "printer_connection_works", "label": "Printer connection works", "type": "checkbox"},
            {"name": "shared_folders_work", "label": "Shared folders or network drives work", "type": "checkbox"},
            {"name": "antivirus_active", "label": "Antivirus is active", "type": "checkbox"},
            {"name": "windows_firewall_active", "label": "Windows Firewall is active", "type": "checkbox"},
            {"name": "no_unexpected_errors", "label": "No unexpected error messages appear", "type": "checkbox"},
            {
                "name": "post_cleanup_issues",
                "label": "Issues encountered",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part P: Final Practical Checklist",
        "description": "Final supervisor checklist from the practical document.",
        "fields": [
            {"name": "final_computer_info_recorded", "label": "Computer information recorded", "type": "checkbox"},
            {"name": "final_initial_free_space_recorded", "label": "Initial free disk space recorded", "type": "checkbox"},
            {"name": "final_restore_point_created", "label": "Restore point created", "type": "checkbox"},
            {"name": "final_user_temp_deleted", "label": "User temporary files deleted", "type": "checkbox"},
            {"name": "final_windows_temp_deleted", "label": "Windows temporary files deleted", "type": "checkbox"},
            {"name": "final_recycle_bin_emptied", "label": "Recycle Bin emptied", "type": "checkbox"},
            {"name": "final_dns_cache_cleared", "label": "DNS cache cleared", "type": "checkbox"},
            {"name": "final_store_cache_cleared", "label": "Microsoft Store cache cleared", "type": "checkbox"},
            {"name": "final_disk_cleanup_completed", "label": "Disk Cleanup completed", "type": "checkbox"},
            {"name": "final_update_cache_cleared", "label": "Windows Update cache cleared", "type": "checkbox"},
            {"name": "final_update_services_restarted", "label": "Windows Update services restarted", "type": "checkbox"},
            {"name": "final_dism_completed", "label": "DISM repair command completed", "type": "checkbox"},
            {"name": "final_sfc_completed", "label": "System File Checker completed", "type": "checkbox"},
            {"name": "final_windows_updates_checked", "label": "Windows updates checked", "type": "checkbox"},
            {"name": "final_updates_installed", "label": "Approved updates installed", "type": "checkbox"},
            {"name": "final_virtual_memory_enabled", "label": "Automatic virtual memory enabled", "type": "checkbox"},
            {"name": "final_computer_restarted", "label": "Computer restarted", "type": "checkbox"},
            {"name": "final_free_space_recorded", "label": "Final free disk space recorded", "type": "checkbox"},
            {"name": "final_basic_functions_tested", "label": "Basic computer functions tested", "type": "checkbox"},
            {"name": "final_issues_documented", "label": "Issues encountered documented", "type": "checkbox"},
            {"name": "final_verified_by_supervisor", "label": "Work verified by the ICT supervisor", "type": "checkbox"},
        ],
    },
    {
        "title": "Part Q: Issues Encountered During Cleanup",
        "description": "Record up to six cleanup issues.",
        "fields": [
            {"name": "issue_1_task_command", "label": "Issue 1 - Task or Command", "type": "text"},
            {"name": "issue_1_issue_encountered", "label": "Issue 1 - Issue Encountered", "type": "text"},
            {"name": "issue_1_error_message", "label": "Issue 1 - Error Message", "type": "text"},
            {"name": "issue_1_action_taken", "label": "Issue 1 - Action Taken", "type": "text"},
            {"name": "issue_1_status", "label": "Issue 1 - Status", "type": "select", "options": STATUS_OPTIONS},
            {"name": "issue_2_task_command", "label": "Issue 2 - Task or Command", "type": "text"},
            {"name": "issue_2_issue_encountered", "label": "Issue 2 - Issue Encountered", "type": "text"},
            {"name": "issue_2_error_message", "label": "Issue 2 - Error Message", "type": "text"},
            {"name": "issue_2_action_taken", "label": "Issue 2 - Action Taken", "type": "text"},
            {"name": "issue_2_status", "label": "Issue 2 - Status", "type": "select", "options": STATUS_OPTIONS},
            {"name": "issue_3_task_command", "label": "Issue 3 - Task or Command", "type": "text"},
            {"name": "issue_3_issue_encountered", "label": "Issue 3 - Issue Encountered", "type": "text"},
            {"name": "issue_3_error_message", "label": "Issue 3 - Error Message", "type": "text"},
            {"name": "issue_3_action_taken", "label": "Issue 3 - Action Taken", "type": "text"},
            {"name": "issue_3_status", "label": "Issue 3 - Status", "type": "select", "options": STATUS_OPTIONS},
            {"name": "issue_4_task_command", "label": "Issue 4 - Task or Command", "type": "text"},
            {"name": "issue_4_issue_encountered", "label": "Issue 4 - Issue Encountered", "type": "text"},
            {"name": "issue_4_error_message", "label": "Issue 4 - Error Message", "type": "text"},
            {"name": "issue_4_action_taken", "label": "Issue 4 - Action Taken", "type": "text"},
            {"name": "issue_4_status", "label": "Issue 4 - Status", "type": "select", "options": STATUS_OPTIONS},
            {"name": "issue_5_task_command", "label": "Issue 5 - Task or Command", "type": "text"},
            {"name": "issue_5_issue_encountered", "label": "Issue 5 - Issue Encountered", "type": "text"},
            {"name": "issue_5_error_message", "label": "Issue 5 - Error Message", "type": "text"},
            {"name": "issue_5_action_taken", "label": "Issue 5 - Action Taken", "type": "text"},
            {"name": "issue_5_status", "label": "Issue 5 - Status", "type": "select", "options": STATUS_OPTIONS},
            {"name": "issue_6_task_command", "label": "Issue 6 - Task or Command", "type": "text"},
            {"name": "issue_6_issue_encountered", "label": "Issue 6 - Issue Encountered", "type": "text"},
            {"name": "issue_6_error_message", "label": "Issue 6 - Error Message", "type": "text"},
            {"name": "issue_6_action_taken", "label": "Issue 6 - Action Taken", "type": "text"},
            {"name": "issue_6_status", "label": "Issue 6 - Status", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "title": "Part R: Intern's Summary",
        "description": "Intern reflection fields.",
        "fields": [
            {
                "name": "activities_completed",
                "label": "What activities did you complete?",
                "type": "textarea",
                "full_width": True,
            },
            {
                "name": "disk_space_recovered_summary",
                "label": "How much disk space was recovered?",
                "type": "textarea",
                "full_width": True,
            },
            {
                "name": "virtual_memory_learning",
                "label": "What did you learn about virtual memory?",
                "type": "textarea",
                "full_width": True,
            },
            {
                "name": "most_useful_command",
                "label": "Which command was most useful?",
                "type": "textarea",
                "full_width": True,
            },
            {
                "name": "unresolved_problems",
                "label": "What problems remain unresolved?",
                "type": "textarea",
                "full_width": True,
            },
        ],
    },
    {
        "title": "Part S: Supervisor's Assessment",
        "description": "Marks and supervisor comments.",
        "fields": [
            {
                "name": "marks_safety_backup",
                "label": "Observed safety and backup requirements (10)",
                "type": "number",
                "step": "1",
            },
            {
                "name": "marks_computer_info",
                "label": "Recorded computer information correctly (10)",
                "type": "number",
                "step": "1",
            },
            {
                "name": "marks_cleared_temp_cache",
                "label": "Cleared temporary files and caches (20)",
                "type": "number",
                "step": "1",
            },
            {"name": "marks_used_commands", "label": "Used commands correctly (15)", "type": "number", "step": "1"},
            {
                "name": "marks_repair_tools",
                "label": "Ran Windows repair tools (15)",
                "type": "number",
                "step": "1",
            },
            {
                "name": "marks_windows_updates",
                "label": "Checked and installed Windows updates (10)",
                "type": "number",
                "step": "1",
            },
            {
                "name": "marks_virtual_memory",
                "label": "Configured virtual memory correctly (10)",
                "type": "number",
                "step": "1",
            },
            {
                "name": "marks_documented_issues",
                "label": "Documented issues and results (10)",
                "type": "number",
                "step": "1",
            },
            {"name": "marks_total", "label": "Total (100)", "type": "number", "step": "1"},
            {
                "name": "supervisor_comments",
                "label": "Supervisor's comments",
                "type": "textarea",
                "full_width": True,
            },
            {"name": "intern_signature_date", "label": "Intern's signature date", "type": "date"},
            {"name": "supervisor_signature_date", "label": "Supervisor's signature date", "type": "date"},
        ],
    },
]


def iter_fields():
    for section in FIELD_SECTIONS:
        for field in section["fields"]:
            yield field


def blank_form_data() -> dict:
    data = {}
    for field in iter_fields():
        if field["type"] == "checkbox":
            data[field["name"]] = bool(field.get("default", False))
        else:
            data[field["name"]] = field.get("default", "")
    return data


def field_label(field_name: str) -> str:
    for field in iter_fields():
        if field["name"] == field_name:
            return field["label"]
    return field_name.replace("_", " ").title()
