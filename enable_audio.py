#!/usr/bin/env python3
"""
Enable Windows playback (speakers/headphones) and recording (microphone) devices.

Uses built-in PowerShell + optional pycaw for volume/unmute.
Run as Administrator for best results (PnP + registry fixes).

Usage:
  python enable_audio.py              # list + enable + unmute + set defaults
  python enable_audio.py --list-only
  python enable_audio.py --no-defaults
"""

from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
from typing import Any


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_ps(script: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def list_devices() -> dict[str, Any]:
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$pnp = Get-PnpDevice | Where-Object {
    $_.Class -in @('MEDIA','AudioEndpoint','Sound') -or
    $_.FriendlyName -match 'audio|sound|microphone|speaker|headphone|headset|realtek|capture|recording'
} | Select-Object Status, Class, FriendlyName, InstanceId

$render = @()
$capture = @()
$renderRoot = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
$captureRoot = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture'

foreach ($root in @($renderRoot, $captureRoot)) {
  if (-not (Test-Path $root)) { continue }
  Get-ChildItem $root | ForEach-Object {
    $props = Join-Path $_.PSPath 'Properties'
    $p = Get-ItemProperty $props -ErrorAction SilentlyContinue
    $name = $p.'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
    if (-not $name) { $name = '(unnamed)' }
    $state = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DeviceState
    $kind = if ($root -eq $renderRoot) { 'playback' } else { 'recording' }
    $obj = [ordered]@{ kind = $kind; name = $name; device_state = $state; id = $_.PSChildName }
    if ($kind -eq 'playback') { $render += $obj } else { $capture += $obj }
  }
}

[ordered]@{
  admin = ([bool]([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
  pnp = @($pnp)
  playback = @($render)
  recording = @($capture)
} | ConvertTo-Json -Depth 5 -Compress
"""
    code, out, err = run_ps(script)
    if code != 0 or not out:
        raise RuntimeError(err or "Failed to list audio devices")
    return json.loads(out)


def enable_pnp_audio() -> list[str]:
    script = r"""
$ErrorActionPreference = 'Continue'
$logs = @()
$targets = Get-PnpDevice | Where-Object {
    ($_.Class -in @('MEDIA','AudioEndpoint')) -or
    ($_.FriendlyName -match 'audio|sound|microphone|speaker|headphone|headset|realtek|capture|recording')
}
foreach ($d in $targets) {
    if ($d.Status -eq 'OK') { continue }
    try {
        Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null
        $logs += "Enabled PnP: $($d.FriendlyName)"
    } catch {
        $logs += "PnP skip ($($d.Status)): $($d.FriendlyName) — $($_.Exception.Message)"
    }
}
$logs -join "`n"
"""
    _, out, err = run_ps(script)
    lines = [ln for ln in (out or err).splitlines() if ln.strip()]
    return lines


def enable_mmdevice_endpoints() -> list[str]:
    """Re-enable disabled endpoints in MMDevices registry (requires admin)."""
    script = r"""
$ErrorActionPreference = 'Stop'
$ACTIVE = 0x10000001
$logs = @()
$roots = @{
    'playback'  = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
    'recording' = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture'
}
foreach ($kv in $roots.GetEnumerator()) {
    $root = $kv.Value
    if (-not (Test-Path $root)) { continue }
    Get-ChildItem $root | ForEach-Object {
        $path = $_.PSPath
        $cur = (Get-ItemProperty $path -Name DeviceState -ErrorAction SilentlyContinue).DeviceState
        if ($null -eq $cur) { return }
        if ($cur -eq $ACTIVE) { return }
        $props = Join-Path $path 'Properties'
        $name = (Get-ItemProperty $props -ErrorAction SilentlyContinue).'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
        if (-not $name) { $name = $_.PSChildName }
        try {
            Set-ItemProperty -Path $path -Name DeviceState -Value $ACTIVE -Type DWord
            $logs += "Registry enabled $($kv.Key): $name"
        } catch {
            $logs += "Registry failed $($kv.Key): $name — $($_.Exception.Message)"
        }
    }
}
if (-not $logs.Count) { 'No disabled MMDevices endpoints changed (or none found).' }
else { $logs -join "`n" }
"""
    _, out, err = run_ps(script)
    text = out or err
    return [ln for ln in text.splitlines() if ln.strip()]


def enable_microphone_privacy() -> list[str]:
    script = r"""
$logs = @()
$paths = @(
    @{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone'; Name = 'Value'; Want = 'Allow' },
    @{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged'; Name = 'Value'; Want = 'Allow' }
)
foreach ($p in $paths) {
    if (-not (Test-Path $p.Path)) {
        New-Item -Path $p.Path -Force | Out-Null
    }
  try {
        Set-ItemProperty -Path $p.Path -Name $p.Name -Value $p.Want -Force
        $logs += "Privacy: set $($p.Path) = Allow"
    } catch {
        $logs += "Privacy failed: $($p.Path) — $($_.Exception.Message)"
    }
}
$logs -join "`n"
"""
    _, out, err = run_ps(script)
    return [ln for ln in (out or err).splitlines() if ln.strip()]


def set_default_devices_powershell() -> list[str]:
    """Set first available playback/recording endpoint as default via PolicyConfig COM."""
    script = r"""
$ErrorActionPreference = 'Stop'
$logs = @()

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace AudioDefaults {
  [ComImport, Guid("870AF99C-1717-40B1-AFEB-BC44CE4A207C")]
  public class PolicyConfigClient { }
  [Guid("F86766F9-AA88-4B80-B7DC-77EDC57E8992"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IPolicyConfig {
    int Reserved1(); int Reserved2(); int Reserved3(); int Reserved4(); int Reserved5();
    int Reserved6(); int Reserved7(); int Reserved8(); int Reserved9(); int Reserved10();
    [PreserveSig] int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string deviceId, int role);
  }
  public enum ERole { eConsole = 0, eMultimedia = 1, eCommunications = 2 }
}
'@

function Set-Default-ForFlow($flowName, $registryRoot) {
  $policy = [AudioDefaults.PolicyConfigClient]::new()
  $iface = [AudioDefaults.IPolicyConfig]$policy
  $picked = $null
  if (Test-Path $registryRoot) {
    Get-ChildItem $registryRoot | ForEach-Object {
      if ($picked) { return }
      $state = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DeviceState
      if ($state -ne 0x10000001) { return }
      $id = $_.PSChildName
      $props = Join-Path $_.PSPath 'Properties'
      $name = (Get-ItemProperty $props -ErrorAction SilentlyContinue).'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
      $picked = @{ id = $id; name = $name }
    }
  }
  if (-not $picked) {
    $script:logs += "No active $flowName endpoint to set as default."
    return
  }
  $devId = "{0.0.0.00000000}." + $picked.id
  foreach ($role in [AudioDefaults.ERole]::GetEnumValues()) {
    [void]$iface.SetDefaultEndpoint($devId, [int]$role)
  }
  $script:logs += "Default $flowName : $($picked.name)"
}

$logs = @()
Set-Default-ForFlow 'playback'  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
Set-Default-ForFlow 'recording' 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture'
$logs -join "`n"
"""
    _, out, err = run_ps(script)
    return [ln for ln in (out or err).splitlines() if ln.strip()]


def unmute_via_pycaw() -> list[str]:
  logs: list[str] = []
  try:
    from pycaw.pycaw import AudioUtilities
    from pycaw.constants import EDataFlow
  except ImportError:
    return ["pycaw not installed — skip unmute (pip install pycaw)."]

  for flow, label in ((EDataFlow.eRender, "playback"), (EDataFlow.eCapture, "recording")):
    try:
      devices = AudioUtilities.GetAllDevices(data_flow=flow, deviceState=1)
    except TypeError:
      devices = AudioUtilities.GetAllDevices()
    count = 0
    for dev in devices or []:
      try:
        vol = dev.EndpointVolume
        vol.SetMute(0, None)
        vol.SetMasterVolumeLevelScalar(0.85, None)
        count += 1
        logs.append(f"Unmuted {label}: {getattr(dev, 'FriendlyName', dev)}")
      except Exception:
        continue
    if count == 0:
      logs.append(f"No active {label} endpoints to unmute via pycaw.")
  return logs


def print_report(data: dict[str, Any]) -> None:
    print("\n=== PnP audio-related devices ===")
    for d in data.get("pnp") or []:
        print(f"  [{d.get('Status')}] {d.get('FriendlyName')} ({d.get('Class')})")

    print("\n=== Playback (MMDevices) ===")
    for d in data.get("playback") or []:
        state = d.get("device_state")
        label = "active" if state == 16777217 else f"state=0x{state:X}" if isinstance(state, int) else state
        print(f"  [{label}] {d.get('name')}")

    print("\n=== Recording (MMDevices) ===")
    rec = data.get("recording") or []
    if not rec:
        print("  (none — plug headset/splitter or check pink mic jack)")
    for d in rec:
        state = d.get("device_state")
        label = "active" if state == 16777217 else f"state=0x{state:X}" if isinstance(state, int) else state
        print(f"  [{label}] {d.get('name')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable Windows sound + microphone devices.")
    parser.add_argument("--list-only", action="store_true", help="Only list devices")
    parser.add_argument("--no-defaults", action="store_true", help="Do not change default devices")
    parser.add_argument("--no-privacy", action="store_true", help="Skip microphone privacy registry")
    args = parser.parse_args()

    admin = is_admin()
    print(f"Administrator: {'yes' if admin else 'no (re-run as Admin for full fixes)'}")

    try:
        report = list_devices()
    except RuntimeError as e:
        print(f"Error listing devices: {e}", file=sys.stderr)
        return 1

    print_report(report)

    if args.list_only:
        return 0

    print("\n--- Applying fixes ---\n")

    for line in enable_pnp_audio():
        print(line)

    if admin:
        for line in enable_mmdevice_endpoints():
            print(line)
    else:
        print("Skipped MMDevices registry enable (needs Administrator).")

    if not args.no_privacy:
        for line in enable_microphone_privacy():
            print(line)

    if not args.no_defaults:
        for line in set_default_devices_powershell():
            print(line)

    for line in unmute_via_pycaw():
        print(line)

    print("\n--- After ---\n")
    try:
        print_report(list_devices())
    except RuntimeError:
        pass

    print(
        "\nNote: A single 3.5 mm headset on a desktop often needs a combo jack or "
        "TRRS→dual splitter (green+pink). No script can fix the wrong physical port."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
