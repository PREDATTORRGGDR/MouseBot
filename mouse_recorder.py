import json
import time
import winsound
from pathlib import Path

from pynput import keyboard, mouse


PATTERN_FILE = Path(__file__).with_name("mouse_pattern.json")

recording = False
playing = False
events = []
record_start = 0.0
last_move_time = 0.0

mouse_controller = mouse.Controller()


def now():
    return time.perf_counter()


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
    global last_move_time

    if not recording or playing:
        return

    current_time = now()

    # Keep the recording file small by saving mouse movement every 10 ms.
    if current_time - last_move_time < 0.01:
        return

    last_move_time = current_time
    add_event({"type": "move", "x": x, "y": y})


def on_click(x, y, button, pressed):
    add_event(
        {
            "type": "click",
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
        }
    )


def on_scroll(x, y, dx, dy):
    add_event({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy})


def start_recording():
    global recording, events, record_start, last_move_time

    events = []
    recording = True
    record_start = now()
    last_move_time = 0.0
    beep_start()
    print("Recording started. Move/click/scroll the mouse. Press F8 to stop.")


def stop_recording():
    global recording

    recording = False
    save_events()
    beep_stop()
    print(f"Recording stopped. Events: {len(events)}")
    print(f"File: {PATTERN_FILE}")


def play_events():
    global playing

    if recording:
        beep_error()
        print("Stop recording with F8 before playback.")
        return

    recorded_events = load_events()
    if not recorded_events:
        beep_error()
        print("Recording is empty. Press F8, record actions, then press F6.")
        return

    playing = True
    beep_play()
    print(f"Playback started. Events: {len(recorded_events)}")

    start_time = now()
    for event in recorded_events:
        wait_time = event["t"] - (now() - start_time)
        if wait_time > 0:
            time.sleep(wait_time)

        event_type = event["type"]

        if event_type == "move":
            mouse_controller.position = (event["x"], event["y"])
        elif event_type == "click":
            button = getattr(mouse.Button, event["button"])
            mouse_controller.position = (event["x"], event["y"])
            if event["pressed"]:
                mouse_controller.press(button)
            else:
                mouse_controller.release(button)
        elif event_type == "scroll":
            mouse_controller.position = (event["x"], event["y"])
            mouse_controller.scroll(event["dx"], event["dy"])

    playing = False
    beep_done()
    print("Playback finished.")


def on_key_press(key):
    try:
        if key == keyboard.Key.f8:
            if recording:
                stop_recording()
            else:
                start_recording()

        elif key == keyboard.Key.f6:
            play_events()

        elif key == keyboard.Key.esc:
            beep_exit()
            print("Exit.")
            return False

    except Exception as error:
        beep_error()
        print(f"Error: {error}")


def main():
    print("Mouse recorder started.")
    print("F8 - start/stop recording")
    print("F6 - play recording")
    print("Esc - exit")
    print(f"Recording file: {PATTERN_FILE}")

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
