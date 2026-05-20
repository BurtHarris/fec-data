@{
    ModuleVersion = '0.1.0'
    Author = 'Burt Harris'
    Description = 'Reusable PowerShell ETL helpers with cycle-based raw archive sync for FEC bulk data.'
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