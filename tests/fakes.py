INSTALLED_ACF = '''"AppState"
{
\t"appid"\t\t"240"
\t"name"\t\t"Counter-Strike: Source"
\t"StateFlags"\t\t"4"
\t"installdir"\t\t"Counter-Strike Source"
\t"LastUpdated"\t\t"1776007826"
\t"SizeOnDisk"\t\t"4880436674"
\t"BytesToDownload"\t\t"2716461696"
\t"BytesDownloaded"\t\t"2716461696"
\t"BytesToStage"\t\t"4880436674"
\t"BytesStaged"\t\t"4880436674"
}
'''

DOWNLOADING_ACF = '''"AppState"
{
\t"appid"\t\t"1446890"
\t"name"\t\t"Shadow Fight Arena"
\t"StateFlags"\t\t"2"
\t"installdir"\t\t"Shadow Fight Arena"
\t"LastUpdated"\t\t"1776007826"
\t"SizeOnDisk"\t\t"0"
\t"BytesToDownload"\t\t"7948206080"
\t"BytesDownloaded"\t\t"2384461824"
\t"BytesToStage"\t\t"7948206080"
\t"BytesStaged"\t\t"0"
}
'''

FULL_DOWNLOAD_ACF = '''"AppState"
{
\t"appid"\t\t"730"
\t"name"\t\t"Counter-Strike 2"
\t"StateFlags"\t\t"1026"
\t"installdir"\t\t"Counter-Strike Global Offensive"
\t"LastUpdated"\t\t"1776007826"
\t"SizeOnDisk"\t\t"34000000000"
\t"BytesToDownload"\t\t"5000000000"
\t"BytesDownloaded"\t\t"2500000000"
\t"BytesToStage"\t\t"5000000000"
\t"BytesStaged"\t\t"2500000000"
}
'''

INSTALLED_WITH_UPDATE_ACF = '''"AppState"
{
\t"appid"\t\t"730"
\t"name"\t\t"Counter-Strike 2"
\t"StateFlags"\t\t"6"
\t"installdir"\t\t"Counter-Strike Global Offensive"
\t"BytesToDownload"\t\t"5000000000"
\t"BytesDownloaded"\t\t"1000000000"
}
'''

PARTIAL_DOWNLOAD_ACF = '''"AppState"
{
\t"appid"\t\t"440"
\t"name"\t\t"Team Fortress 2"
\t"StateFlags"\t\t"2"
\t"installdir"\t\t"Team Fortress 2"
\t"BytesToDownload"\t\t"4000000000"
\t"BytesDownloaded"\t\t"0"
}
'''

COMPLETED_DOWNLOAD_ACF = '''"AppState"
{
\t"appid"\t\t"570"
\t"name"\t\t"Dota 2"
\t"StateFlags"\t\t"4"
\t"installdir"\t\t"Dota 2"
\t"BytesToDownload"\t\t"6000000000"
\t"BytesDownloaded"\t\t"6000000000"
\t"BytesToStage"\t\t"6000000000"
\t"BytesStaged"\t\t"3500000000"
}
'''

NO_BYTES_ACF = '''"AppState"
{
\t"appid"\t\t"228980"
\t"name"\t\t"Steamworks Common Redistributables"
\t"StateFlags"\t\t"6"
}
'''

LIBRARY_FOLDERS_VDF = '''"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"
\t}
\t"1"
\t{
\t\t"path"\t\t"D:\\\\SteamLibrary"
\t}
}
'''

EMPTY_LIBRARY_VDF = '''"libraryfolders"
{
}
'''

MALFORMED_ACF = 'AppState\n{\n"appid" "240"\n'
