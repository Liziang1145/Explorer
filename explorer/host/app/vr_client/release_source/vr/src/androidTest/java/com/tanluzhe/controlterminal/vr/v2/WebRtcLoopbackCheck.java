package com.tanluzhe.controlterminal.vr.v2;

import android.content.Context;
import android.os.SystemClock;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.webrtc.*;

/** Device-local synthetic test: no base station address, lease, sensor or robot is used. */
final class WebRtcLoopbackCheck {
  static String run(Context context) throws Exception {
    PeerConnectionFactory.initialize(
        PeerConnectionFactory.InitializationOptions.builder(context).createInitializationOptions());
    EglBase egl = EglBase.create();
    egl.createDummyPbufferSurface();
    egl.makeCurrent();
    AtomicReference<String> error = new AtomicReference<>();
    AtomicInteger decoded = new AtomicInteger(), matched = new AtomicInteger();
    Set<Long> decoderInputs = ConcurrentHashMap.newKeySet();
    CountDownLatch echoed = new CountDownLatch(1);
    HardwareVideoDecoderFactory hardware = new HardwareVideoDecoderFactory(egl.getEglBaseContext());
    VideoDecoderFactory decoder = new VideoDecoderFactory() {
      public VideoCodecInfo[] getSupportedCodecs() {
        return hardware.getSupportedCodecs();
      }
      public VideoDecoder createDecoder(VideoCodecInfo codec) {
        if (!codec.name.equalsIgnoreCase("H264"))
          return null;
        VideoDecoder actual = hardware.createDecoder(codec);
        if (actual == null)
          return null;
        return new VideoDecoder() {
          public VideoCodecStatus initDecode(Settings s, Callback callback) {
            return actual.initDecode(s, (frame, time, qp) -> {
              decoded.incrementAndGet();
              if (decoderInputs.remove(frame.getTimestampNs()))
                matched.incrementAndGet();
              callback.onDecodedFrame(frame, time, qp);
            });
          }
          public VideoCodecStatus decode(EncodedImage image, DecodeInfo info) {
            decoderInputs.add(image.captureTimeNs);
            return actual.decode(image, info);
          }
          public VideoCodecStatus release() {
            return actual.release();
          }
          public String getImplementationName() {
            return actual.getImplementationName();
          }
        };
      }
    };
    PeerConnectionFactory factory = PeerConnectionFactory.builder()
                                        .setVideoEncoderFactory(new HardwareVideoEncoderFactory(
                                            egl.getEglBaseContext(), true, true))
                                        .setVideoDecoderFactory(decoder)
                                        .createPeerConnectionFactory();
    PeerConnection[] pcs = new PeerConnection[2];
    DataChannel[] channel = new DataChannel[1];
    boolean[] ready = {false, false};
    List<List<IceCandidate>> queued = Arrays.asList(new ArrayList<>(), new ArrayList<>());
    VideoSource source = null;
    VideoTrack track = null;
    try {
      PeerConnection.RTCConfiguration config =
          new PeerConnection.RTCConfiguration(Collections.emptyList());
      config.sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN;
      config.tcpCandidatePolicy = PeerConnection.TcpCandidatePolicy.DISABLED;
      for (int i = 0; i < 2; i++) {
        final int side = i;
        pcs[i] = factory.createPeerConnection(config, new PeerConnection.Observer() {
          public void onSignalingChange(PeerConnection.SignalingState s) {}
          public void onIceConnectionChange(PeerConnection.IceConnectionState s) {}
          public void onIceConnectionReceivingChange(boolean b) {}
          public void onIceGatheringChange(PeerConnection.IceGatheringState s) {}
          public void onIceCandidate(IceCandidate ice) {
            int target = 1 - side;
            synchronized (queued) {
              if (ready[target])
                pcs[target].addIceCandidate(ice);
              else
                queued.get(target).add(ice);
            }
          }
          public void onIceCandidatesRemoved(IceCandidate[] a) {}
          public void onAddStream(MediaStream s) {}
          public void onRemoveStream(MediaStream s) {}
          public void onRenegotiationNeeded() {}
          public void onTrack(RtpTransceiver t) {
            if (t.getReceiver().track() instanceof VideoTrack)
              ((VideoTrack) t.getReceiver().track()).addSink(frame -> {});
          }
          public void onDataChannel(DataChannel c) {
            c.registerObserver(new DataChannel.Observer() {
              public void onStateChange() {}
              public void onBufferedAmountChange(long a) {}
              public void onMessage(DataChannel.Buffer b) {
                byte[] bytes = new byte[b.data.remaining()];
                b.data.get(bytes);
                try {
                  Packet packet = Packet.decode(bytes);
                  if (packet.type != Packet.PING)
                    throw new AssertionError("Unexpected loopback type");
                  c.send(new DataChannel.Buffer(ByteBuffer.wrap(bytes), true));
                } catch (Throwable e) {
                  error.set(e.toString());
                }
              }
            });
          }
        });
        if (pcs[i] == null)
          throw new AssertionError("PeerConnection null");
      }
      source = factory.createVideoSource(false);
      track = factory.createVideoTrack("synthetic-h264", source);
      pcs[0].addTrack(track);
      List<RtpCapabilities.CodecCapability> h264 = new ArrayList<>();
      for (RtpCapabilities.CodecCapability c :
          factory.getRtpSenderCapabilities(MediaStreamTrack.MediaType.MEDIA_TYPE_VIDEO).codecs)
        if (c.name.equalsIgnoreCase("H264"))
          h264.add(c);
      if (h264.isEmpty())
        throw new AssertionError("No hardware H.264 capability");
      pcs[0].getTransceivers().get(0).setCodecPreferences(h264);
      DataChannel.Init init = new DataChannel.Init();
      init.ordered = false;
      init.maxRetransmits = 0;
      init.protocol = "tlz/2.0";
      channel[0] = pcs[0].createDataChannel("tlz.probe.v2", init);
      Packet packet = new Packet();
      packet.session = 1;
      packet.node = 2;
      packet.stream = 103;
      packet.epoch = 1;
      packet.seq = 1;
      packet.time = System.nanoTime();
      packet.ttlMs = 1000;
      packet.type = Packet.PING;
      packet.body = Cbor.map(0, 1, 1, packet.time, 2, 1, 3, 0);
      byte[] bytes = packet.encode();
      channel[0].registerObserver(new DataChannel.Observer() {
        public void onStateChange() {}
        public void onBufferedAmountChange(long a) {}
        public void onMessage(DataChannel.Buffer b) {
          byte[] reply = new byte[b.data.remaining()];
          b.data.get(reply);
          if (Arrays.equals(reply, bytes))
            echoed.countDown();
          else
            error.set("DataChannel echo mismatch");
        }
      });
      pcs[0].createOffer(new Sdp() {
        public void onCreateSuccess(SessionDescription offer) {
          pcs[0].setLocalDescription(new Sdp(), offer);
          pcs[1].setRemoteDescription(new Sdp() {
            public void onSetSuccess() {
              flush(1, pcs, ready, queued);
              pcs[1].createAnswer(new Sdp() {
                public void onCreateSuccess(SessionDescription answer) {
                  pcs[1].setLocalDescription(new Sdp(), answer);
                  pcs[0].setRemoteDescription(new Sdp() {
                    public void onSetSuccess() {
                      flush(0, pcs, ready, queued);
                    }
                  }, answer);
                }
              }, new MediaConstraints());
            }
          }, offer);
        }
      }, new MediaConstraints());
      source.getCapturerObserver().onCapturerStarted(true);
      long deadline = System.nanoTime() + 12_000_000_000L;
      int sent = 0;
      boolean pingSent = false;
      while (System.nanoTime() < deadline) {
        if (!pingSent && channel[0].state() == DataChannel.State.OPEN) {
          channel[0].send(new DataChannel.Buffer(ByteBuffer.wrap(bytes), true));
          pingSent = true;
        }
        JavaI420Buffer pixels = JavaI420Buffer.allocate(320, 240);
        fill(pixels.getDataY(), pixels.getStrideY(), 320, 240, (byte) (80 + sent % 30));
        fill(pixels.getDataU(), pixels.getStrideU(), 160, 120, (byte) 128);
        fill(pixels.getDataV(), pixels.getStrideV(), 160, 120, (byte) 128);
        VideoFrame frame = new VideoFrame(pixels, 0, System.nanoTime());
        source.getCapturerObserver().onFrameCaptured(frame);
        frame.release();
        sent++;
        if (decoded.get() >= 5 && matched.get() >= 5 && echoed.getCount() == 0)
          break;
        SystemClock.sleep(67);
      }
      if (error.get() != null)
        throw new AssertionError(error.get());
      if (echoed.getCount() != 0 || decoded.get() < 5 || matched.get() < 5)
        throw new AssertionError("Loopback incomplete: echo=" + (echoed.getCount() == 0)
            + ",decoded=" + decoded + ",timestamp_matches=" + matched);
      return "PASS: unordered zero-retransmit TLZ2 DataChannel echo; hardware H264 decoded="
          + decoded + "; decoder frame timestamps matched=" + matched;
    } finally {
      for (PeerConnection p : pcs)
        if (p != null)
          p.close();
      if (track != null)
        track.dispose();
      if (source != null)
        source.dispose();
      for (PeerConnection p : pcs)
        if (p != null)
          p.dispose();
      factory.dispose();
      egl.release();
    }
  }
  private static void fill(ByteBuffer b, int stride, int width, int height, byte value) {
    for (int y = 0; y < height; y++)
      for (int x = 0; x < width; x++) b.put(y * stride + x, value);
  }
  private static void flush(
      int side, PeerConnection[] pcs, boolean[] ready, List<List<IceCandidate>> queues) {
    synchronized (queues) {
      ready[side] = true;
      for (IceCandidate c : queues.get(side)) pcs[side].addIceCandidate(c);
      queues.get(side).clear();
    }
  }
  private static class Sdp implements SdpObserver {
    public void onCreateSuccess(SessionDescription s) {}
    public void onSetSuccess() {}
    public void onCreateFailure(String s) {}
    public void onSetFailure(String s) {}
  }
}
