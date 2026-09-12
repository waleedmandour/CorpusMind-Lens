; Custom NSIS installer hooks for CorpusMind Lens (Tauri v2).
;
; WHY THIS EXISTS
; The app ships a Python engine sidecar (lens-engine.exe) that runs as a
; child process of the desktop shell. The stock Tauri NSIS template only
; stops the MAIN executable before copying files — it does NOT know about
; the sidecar. If the engine process is still alive (app crashed,
; force-closed from Task Manager, or the child outlived its parent),
; Windows locks lens-engine\*.exe and the installer/upgrade fails with
; "Error opening file for writing" (same failure class as Tauri issue
; #15134, sidecar not replaced on reinstall).
;
; These hooks stop BOTH processes (tree-kill) before any file operation
; and give Defender a moment to release freshly-scanned handles.
;
; NOTE: the parent CorpusMind (Text) ships its own corpusmind-engine.exe
; on the same port range. Killing `lens-engine.exe` here is intentional
; and scoped to Lens only — an in-flight Lens engine must be replaced
; atomically, and the next app start simply spawns (or reuses) a fresh
; engine. The parent product's processes are left untouched.

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping any running CorpusMind Lens processes..."
  nsExec::Exec 'taskkill /F /T /IM "lens-engine.exe"'
  nsExec::Exec 'taskkill /F /T /IM "CorpusMind Lens.exe"'
  Sleep 800
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Stopping any running CorpusMind Lens processes..."
  nsExec::Exec 'taskkill /F /T /IM "lens-engine.exe"'
  nsExec::Exec 'taskkill /F /T /IM "CorpusMind Lens.exe"'
  Sleep 800
!macroend
