# Crea 2 tareas en el Programador de tareas de Windows (solo para tu usuario):
#   - Barrido completo todos los días a las 08:00
#   - Vigilancia rápida cada 30 minutos entre 07:00 y 23:59
# Para quitarlas: Unregister-ScheduledTask -TaskName "PokemonTCG*" -Confirm:$false
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
           -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

$barrido = New-ScheduledTaskAction -Execute "$dir\barrido.bat" -WorkingDirectory $dir
Register-ScheduledTask -TaskName "PokemonTCG - Barrido diario" -Action $barrido -Settings $ajustes -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At "08:00") | Out-Null

$vigilar = New-ScheduledTaskAction -Execute "$dir\vigilar.bat" -WorkingDirectory $dir
$disparador = New-ScheduledTaskTrigger -Daily -At "07:00"
$disparador.Repetition = (New-ScheduledTaskTrigger -Once -At "07:00" `
  -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 17)).Repetition
Register-ScheduledTask -TaskName "PokemonTCG - Vigilancia" -Action $vigilar -Settings $ajustes -Force `
  -Trigger $disparador | Out-Null

Write-Host "Listo. Tareas creadas:" -ForegroundColor Green
Get-ScheduledTask -TaskName "PokemonTCG*" | Select-Object TaskName, State
