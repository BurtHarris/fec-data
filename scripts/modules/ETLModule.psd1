@{
    ModuleVersion = '0.1.0'
    Author = 'Burt Harris'
    Description = 'Reusable PowerShell ETL helpers with cycle-based bronze archive sync for FEC bulk data (medallion architecture).'
    RootModule = 'ETLModule.psm1'
    FunctionsToExport = @(
        'Sync-EtlArchiveSet',
        'Invoke-FecCycleRawSync',
        'Expand-EtlCycleArchives',
        'Invoke-EtlCycleLoad'
    )
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}