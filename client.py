import logging
import requests
import json
import argparse
import asyncio
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.codecs import PCMU_CODEC
from aiortc.rtcrtpreceiver import RTCRtpReceiver
from aiortc.rtcrtpparameters import RTCRtpReceiveParameters
from aiortc.contrib.media import MediaRecorder

# receiver = RTCRtpReceiver()

class SignalingClient:
    def __init__(self, server_url):
        self.server_url = server_url

    def retrieve_offer(self):
        res = requests.get(self.server_url + "/getOffer")
        return res.json()

    def send_answer(self, local_description):
        resp = requests.post(self.server_url + "/answer", 
                             data = {"type": local_description.type, "data": local_description.sdp},
                             headers={"Content-Type": "application/json"}
                            )
        if resp.status_code != 200:
            print(f"Error while sending answer: {resp.status_code} {resp.reason}")


async def start_receiving_stream(pc, recorder, server_url):
    @pc.on("connectionstatechange")
    def on_connectionstatechange(x=None):
        print(f"connectionstatechange: {pc.connectionState}")

    @pc.on("signalingstatechange")
    def on_signalingstatechange(x=None):
        print(f"signalingstatechange: {pc.signalingState}")

    @pc.on("icegatherstatechange")
    def on_signalingstatechange(x=None):
        print(f"pc.iceGatheringState: {pc.iceGatheringState}")

    @pc.on("iceconnectionstatechange")
    def on_signalingstatechange(x=None):
        print(f"pc.iceConnectionState: {pc.iceConnectionState}")

    @pc.on("icecandidate")
    def on_icecandidate(candidate):
        print(f"{candidate=}")

    @pc.on("track")
    def on_track(track):
        print(f"Received Track: {track.kind}")

    @pc.on("ended")
    async def on_ended():
        print("Ended")
        await recorder.stop()

    signaling_client = SignalingClient(server_url)

    offer_data = signaling_client.retrieve_offer()
    await pc.setRemoteDescription(RTCSessionDescription(**offer_data))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await recorder.start()
    signaling_client.send_answer(pc.localDescription)

    # print(pc.getReceivers()[0].track.readyState)
    # receiver = pc.getReceivers()[0]
    # await receiver.receive(RTCRtpReceiveParameters(codecs=[PCMU_CODEC]))

if __name__ == "__main__": 

    parser = argparse.ArgumentParser(description="Connect to Record3D")
    parser.add_argument("-u", "--server_url", default="127.0.0.1")

    args = parser.parse_args()
    server_url = f"http://{args.server_url}"

    pc = RTCPeerConnection()
    recorder = MediaRecorder("test.mp4")

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(start_receiving_stream(pc, recorder, server_url))
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(recorder.stop())
        loop.run_until_complete(pc.close())

