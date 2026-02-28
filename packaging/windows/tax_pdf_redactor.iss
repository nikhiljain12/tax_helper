AppName=Tax PDF Redactor
AppVersion=0.1.0
DefaultDirName={autopf}\Tax PDF Redactor
DefaultGroupName=Tax PDF Redactor
OutputBaseFilename=TaxPDFRedactorSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\TaxPDFRedactor\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tax PDF Redactor"; Filename: "{app}\TaxPDFRedactor.exe"
Name: "{group}\Uninstall Tax PDF Redactor"; Filename: "{uninstallexe}"
