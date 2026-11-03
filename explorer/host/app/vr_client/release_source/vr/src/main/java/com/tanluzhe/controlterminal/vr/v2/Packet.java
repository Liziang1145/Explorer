package com.tanluzhe.controlterminal.vr.v2;
import java.nio.*;
import java.util.*;

public final class Packet {
  public static final int CONTROL = 0x101, STATE = 0x102, RECEIPT = 0x103, OPERATOR = 0x104,
                          STOP = 0x105, TIME_REQ = 0x201, TIME_RESP = 0x202, PING = 0x203,
                          PONG = 0x204, STATS = 0x205, CLOUD = 0x301, TILE = 0x302, SCENE = 0x303,
                          VIDEO_META = 0x401;
  public int type, node, stream, epoch, ttlMs;
  public long session, seq, time, trace;
  public Map<Long, Object> body;
  public byte[] encode() {
    byte[] p = Cbor.encode(body);
    if (p.length > 1036)
      throw new IllegalArgumentException("TLZ payload too large");
    ByteBuffer b = ByteBuffer.allocate(64 + p.length).order(ByteOrder.BIG_ENDIAN);
    b.putInt(0x544c5a32)
        .put((byte) 2)
        .put((byte) 0)
        .putShort((short) type)
        .putShort((short) 0)
        .putShort((short) 64)
        .putInt(p.length);
    b.putLong(session)
        .putInt(node)
        .putInt(stream)
        .putLong(seq)
        .putLong(time)
        .putInt(epoch)
        .putInt(ttlMs)
        .putLong(trace)
        .put(p);
    return b.array();
  }
  public static Packet decode(byte[] bytes) {
    if (bytes.length < 65 || bytes.length > 1100)
      throw new IllegalArgumentException("TLZ length");
    ByteBuffer b = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
    if (b.getInt() != 0x544c5a32 || b.get() != 2 || b.get() != 0)
      throw new IllegalArgumentException("TLZ version");
    Packet p = new Packet();
    p.type = b.getShort() & 65535;
    if (b.getShort() != 0 || b.getShort() != 64 || b.getInt() != bytes.length - 64)
      throw new IllegalArgumentException("TLZ header");
    p.session = b.getLong();
    p.node = b.getInt();
    p.stream = b.getInt();
    p.seq = b.getLong();
    p.time = b.getLong();
    p.epoch = b.getInt();
    p.ttlMs = b.getInt();
    p.trace = b.getLong();
    if (p.session == 0 || p.seq == 0 || p.time < 0 || p.ttlMs < 0)
      throw new IllegalArgumentException("TLZ IDs/time");
    p.body = Cbor.object(Cbor.decode(Arrays.copyOfRange(bytes, 64, bytes.length)));
    return p;
  }
}
