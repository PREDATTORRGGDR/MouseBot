import ctypes
import json
import threading
import time
import winsound
from pathlib import Path

from pynput import keyboard, mouse


PATTERN_FILE = Path(__file__).with_name("mouse_pattern.json")
PLAYBACK_DELAY_SEC = 2.0

recording = False
playing = False
stop_requested = False
events = []
record_start = 0.0
last_move_time = 0.0
last_move_x = None
last_move_y = None


PUL = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT)]


INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

VK_F6 = 0x75


def now():
    return time.perf_counter()


def send_mouse_input(flags, dx=0, dy=0, mouse_data=0):
    extra = ctypes.c_ulong(0)
    mouse_input = MOUSEINPUT(dx, dy, mouse_data, flags, 0, ctypes.pointer(extra))
    command = INPUT(type=INPUT_MOUSE, mi=mouse_input)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))


def is_f6_held():
    return (ctypes.windll.user32.GetAsyncKeyState(VK_F6) & 0x8000) != 0


def beep_start():
    winsound.Beep(1000, 120)


def beep_stop():
    winsound.Beep(700, 120)


def beep_play():
    winsound.Beep(1200, 80)
    winsound.Beep(1500, 80)


def beep_done():
    winsound.Beep(900, 80)
    winsound.Beep(650, 80)


def beep_error():
    winsound.Beep(300, 180)


def beep_exit():
    winsound.Beep(500, 80)
    winsound.Beep(400, 80)


def save_events():
    PATTERN_FILE.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_events():
    if not PATTERN_FILE.exists():
        beep_error()
        print(f"Recording file not found: {PATTERN_FILE}")
        return []
    return json.loads(PATTERN_FILE.read_text(encoding="utf-8"))


def add_event(event):
    if not recording or playing:
        return
    event["t"] = now() - record_start
    events.append(event)


def on_move(x, y):
    global last_move_time, last_move_x, last_move_y

    if not recording or playing:
        return

    current_time = now()
    if current_time - last_move_time < 0.01:
        return

    if last_move_x is None or last_move_y is None:
        last_move_x = x
        last_move_y = y
        last_move_time = current_time
        return

    dx = int(x - last_move_x)
    dy = int(y - last_move_y)

    if dx != 0 or dy != 0:
        add_event({"type": "move", "dx": dx, "dy": dy})

    last_move_x = x
    last_move_y = y
    last_move_time = current_time


def on_click(_x, _y, button, pressed):
    add_event({"type": "click", "button": button.name, "pressed": pressed})


def on_scroll(_x, _y, _dx, dy):
    add_event({"type": "scroll", "wheel": int(dy * 120)})


def start_recording():
    global recording, events, record_start, last_move_time, last_move_x, last_move_y

    events = []
    recording = True
    record_start = now()
    last_move_time = 0.0
    last_move_x = None
    last_move_y = None
    beep_start()
    print("Recording started. Move/click/scroll mouse. Press F8 to stop.")


def stop_recording():
    global recording
    recording = False
    save_events()
    beep_stop()
    print(f"Recording stopped. Events: {len(events)}")
    print(f"File: {PATTERN_FILE}")


def apply_event(event):
    event_type = event["type"]
    if event_type == "move":
        send_mouse_input(MOUSEEVENTF_MOVE, event["dx"], event["dy"], 0)
    elif event_type == "click":
        button = event["button"]
        pressed = event["pressed"]
        if button == "left":
            send_mouse_input(MOUSEEVENTF_LEFTDOWN if pressed else MOUSEEVENTF_LEFTUP)
        elif button == "right":
            send_mouse_input(MOUSEEVENTF_RIGHTDOWN if pressed else MOUSEEVENTF_RIGHTUP)
        elif button == "middle":
            send_mouse_input(MOUSEEVENTF_MIDDLEDOWN if pressed else MOUSEEVENTF_MIDDLEUP)
    elif event_type == "scroll":
        send_mouse_input(MOUSEEVENTF_WHEEL, 0, 0, event["wheel"])


def playback_worker(recorded_events):
    global playing, stop_requested

    try:
        print(f"Playback in {PLAYBACK_DELAY_SEC:.1f}s. Switch to target window now.")
        time.sleep(PLAYBACK_DELAY_SEC)
        if stop_requested:
            print("Playback canceled before start.")
            return

        beep_play()
        print(f"Playback started. Events: {len(recorded_events)}")
        start_time = now()

        for event in recorded_events:
            if stop_requested:
                print("Playback stopped by F7.")
                break

            wait_time = event["t"] - (now() - start_time)
            if wait_time > 0:
                time.sleep(wait_time)

            apply_event(event)
    finally:
        playing = False
        stop_requested = False
        beep_done()
        print("Playback finished.")


def start_playback():
    global playing, stop_requested

    if recording:
        beep_error()
        print("Stop recording with F8 before playback.")
        return
    if playing:
        beep_error()
        print("Playback already running. Press F7 to stop.")
        return

    recorded_events = load_events()
    if not recorded_events:
        beep_error()
        print("Recording is empty. Press F8, record actions, then press F6.")
        return

    playing = True
    stop_requested = False
    worker = threading.Thread(target=playback_worker, args=(recorded_events,), daemon=True)
    worker.start()


def stop_playback():
    global stop_requested
    if playing:
        stop_requested = True
        beep_stop()
        print("Stop requested...")


def on_key_press(key):
    try:
        if key == keyboard.Key.f8:
            if recording:
                stop_recording()
            else:
                start_recording()
        elif key == keyboard.Key.f6:
            start_playback()
        elif key == keyboard.Key.f7:
            stop_playback()
        elif key == keyboard.Key.esc:
            if playing:
                stop_playback()
                time.sleep(0.15)
            beep_exit()
            print("Exit.")
            return False
    except Exception as error:
        beep_error()
        print(f"Error: {error}")


def main():
    print("Mouse recorder started.")
    print("F8 - start/stop recording")
    print("F6 - play recording (with short delay)")
    print("F7 - stop playback")
    print("Esc - exit")
    print(f"Recording file: {PATTERN_FILE}")
    print(f"Tip: hold F6 in target app to keep focus. Held: {is_f6_held()}")

    mouse_listener = mouse.Listener(
        on_move=on_move,
        on_click=on_click,
        on_scroll=on_scroll,
    )
    keyboard_listener = keyboard.Listener(on_press=on_key_press)

    mouse_listener.start()
    keyboard_listener.start()
    keyboard_listener.join()
    mouse_listener.stop()


if __name__ == "__main__":
    main()
