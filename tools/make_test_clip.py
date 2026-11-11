"""Build a self-made two-speaker English test clip with known transcript and timings."""
import asyncio, json, os, subprocess, sys
import edge_tts

out = sys.argv[1]
LINES = [
    ("A", "Good morning, Linh. Did you finish the report for the client?"),
    ("B", "Almost. I still need to check the numbers from last month."),
    ("A", "The meeting starts at ten, so we have less than an hour."),
    ("B", "Don't worry. Give me twenty minutes and it will be ready."),
    ("A", "Great. By the way, my sister is visiting this weekend."),
    ("B", "Really? You should take her to the old market near the river."),
    ("A", "That's a good idea. She loves street food, especially noodle soup."),
    ("B", "Then I will send you the address of my favorite place."),
    ("A", "Thank you. Now let's get back to work before the boss arrives."),
]
VOICES = {"A": "en-US-GuyNeural", "B": "en-US-JennyNeural"}
proxy = os.environ.get("HTTPS_PROXY")

def dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]))

async def main():
    t, truth, inputs, delays = 0.8, [], [], []
    for i, (who, text) in enumerate(LINES):
        p = f"{out}/line{i}.mp3"
        await edge_tts.Communicate(text, VOICES[who], proxy=proxy).save(p)
        d = dur(p)
        truth.append({"index": i + 1, "speaker": who, "start": round(t, 2), "end": round(t + d, 2), "text": text})
        inputs += ["-i", p]; delays.append(int(t * 1000)); t += d + 0.7
    total = t + 0.5
    json.dump(truth, open(f"{out}/truth.json", "w"), indent=1)
    mix = "".join(f"[{i+1}:a]adelay={ms}:all=1[a{i}];" for i, ms in enumerate(delays))
    mix += "".join(f"[a{i}]" for i in range(len(delays))) + f"amix=inputs={len(delays)}:normalize=0[speech];"
    # quiet background tone so there is a "music bed" to preserve
    mix += f"sine=frequency=196:duration={total:.2f},volume=0.04[bed];[speech][bed]amix=inputs=2:normalize=0:duration=longest[a]"
    boxes = ",".join(
        f"drawbox=x={'40' if l['speaker']=='A' else '360'}:y=120:w=240:h=240:color={'blue' if l['speaker']=='A' else 'red'}:t=fill:enable='between(t,{l['start']},{l['end']})'"
        for l in truth)
    subprocess.check_call(["ffmpeg","-y","-v","error","-f","lavfi","-i",f"color=c=gray:s=640x480:r=25:d={total:.2f}",
        *inputs,"-filter_complex",f"[0:v]{boxes}[v];{mix}","-map","[v]","-map","[a]","-c:v","libx264","-pix_fmt","yuv420p",
        "-c:a","aac","-t",f"{total:.2f}",f"{out}/source.mp4"])
    print("source", round(total,1), "s")
asyncio.run(main())
