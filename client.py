import asyncio
import json
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder
from av import VideoFrame
import cv2


class SignalingServer:
    def __init__(self, server_url):
        self.server_url = server_url

    async def retrieve_offer(self):
        server_url = f"{self.server_url}/getOffer"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(server_url) as resp:
                    return await resp.json()
            except Exception as e:
                print(f"Error while requesting an offer: {e}")

    async def send_answer(self, answer):
        json_answer = json.dumps(answer)
        server_url = f"{self.server_url}/answer"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    server_url,
                    headers={"Content-Type": "application/json"},
                    data=json_answer,
                ) as resp:
                    await resp.text()
            except Exception as e:
                print(f"Error while sending the answer: {e}")


async def start_receiving_stream(server_url):
    signaling_server = SignalingServer(server_url)
    peer_connection = RTCPeerConnection()

    video_display_running = True

    # Create a MediaRecorder to save the video
    recorder = MediaRecorder("output.mp4")

    @peer_connection.on("track")
    async def on_track(track):
        print(f"Received {track.kind} track")
        if track.kind == "video":
            print("Adding track to recorder")
            print("Starting video display")
            asyncio.create_task(display_video(track))
            recorder.addTrack(track)
            await recorder.start()

    @peer_connection.on("datachannel")
    def on_datachannel(channel):
        print(f"Received data channel: {channel.label}")

    async def display_video(track):
        while video_display_running:
            try:
                frame = await track.recv()
                if isinstance(frame, VideoFrame):
                    # Convert the VideoFrame to a numpy array
                    img = frame.to_ndarray(format="bgr24")

                    # Display the frame using OpenCV
                    cv2.imshow("Video Stream", img)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
            except Exception as e:
                print(f"Error displaying video: {e}")
                break

        cv2.destroyAllWindows()

    # 1. Ask the device for its offer
    remote_offer = await signaling_server.retrieve_offer()
    if remote_offer is None:
        return

    # 2. Set the offer as the remote description, generate a suitable answer for it
    #    and set the answer as the local description.
    await peer_connection.setRemoteDescription(
        RTCSessionDescription(sdp=remote_offer["sdp"], type=remote_offer["type"])
    )
    answer = await peer_connection.createAnswer()
    await peer_connection.setLocalDescription(answer)

    # 3. Wait for the ICE gathering to complete
    while True:
        if peer_connection.iceGatheringState == "complete":
            break
        await asyncio.sleep(0.1)

    # Send answer to the device
    json_data = {"type": "answer", "data": peer_connection.localDescription.sdp}
    await signaling_server.send_answer(json_data)
    print("Finished ice candidate lookup. Sending answer.")

    # Keep the connection alive
    try:
        await asyncio.Future()
    finally:
        video_display_running = False
        await peer_connection.close()
        await recorder.stop()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        remote_address = sys.argv[1]
        if not remote_address.startswith("http://"):
            remote_address = "http://" + remote_address
        print(f"Remote ip: {remote_address}")
        asyncio.run(start_receiving_stream(remote_address))
    else:
        print("Please provide the remote address as an argument.")
