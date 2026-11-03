package com.tanluzhe.controlterminal.vr.v2;
/** Strict single HTTP byte range, including suffix and open-ended requests. */
public final class FileByteRange {
  public final long start, end;
  public final boolean partial;
  private FileByteRange(long start, long end, boolean partial) {
    this.start   = start;
    this.end     = end;
    this.partial = partial;
  }
  public long length() {
    return Math.max(0, end - start + 1);
  }
  public static FileByteRange parse(String range, long length) {
    if (range == null)
      return new FileByteRange(0, length - 1, false);
    if (length <= 0 || !range.matches("bytes=[0-9]*-[0-9]*"))
      throw new IllegalArgumentException("无效单段Range");
    String[] pair = range.substring(6).split("-", -1);
    try {
      long start, end;
      if (pair[0].isEmpty()) {
        if (pair[1].isEmpty())
          throw new IllegalArgumentException();
        long suffix = Long.parseLong(pair[1]);
        if (suffix <= 0)
          throw new IllegalArgumentException();
        start = Math.max(0, length - suffix);
        end   = length - 1;
      } else {
        start = Long.parseLong(pair[0]);
        end   = pair[1].isEmpty() ? length - 1 : Math.min(length - 1, Long.parseLong(pair[1]));
        if (start >= length || end < start)
          throw new IllegalArgumentException();
      }
      return new FileByteRange(start, end, true);
    } catch (NumberFormatException e) {
      throw new IllegalArgumentException("无效Range长度");
    }
  }
}
