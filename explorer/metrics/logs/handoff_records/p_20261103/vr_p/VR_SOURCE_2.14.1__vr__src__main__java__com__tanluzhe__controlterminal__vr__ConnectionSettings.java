package com.tanluzhe.controlterminal.vr;
import android.content.*;
import android.net.*;
import java.net.Inet4Address;
/** Current client settings; migrate only the prior address preference. */
public final class ConnectionSettings {
  public final boolean automatic;
  public final String manualHost, token;
  public final int port, telemetryPort, observationHz;
  public final float press, release, deadzone;
  public ConnectionSettings(Context c) {
    SharedPreferences p = c.getSharedPreferences("v2", 0);
    if (!p.getBoolean("aipc_direct_20261022",false)) {
      String saved=p.getString("host","");int savedPort=p.getInt("port",8080);
      boolean old=p.getBoolean("automatic",true)||saved.isEmpty()||saved.equals("192.168.2.1")||saved.equals("192.168.137.131")||saved.equals("192.168.137.1");
      SharedPreferences.Editor edit=p.edit().putBoolean("aipc_direct_20261022",true).putBoolean("automatic",false).remove("pin");
      if(old) edit.putString("host","192.168.137.2").putInt("port",8088);
      else if(savedPort==8080||savedPort==8443)edit.putInt("port",8088);
      edit.commit();
    }
    automatic = p.getBoolean("automatic", false);
    manualHost = p.getString("host", "192.168.137.2");
    port = p.getInt("port", 8088);
    telemetryPort=p.getInt("telemetry_port",8092);
    String secret = p.getString("token", "1");
    token = secret.trim().isEmpty() ? "1" : secret;
    observationHz = p.getInt("observation_hz", 50);
    press = p.getFloat("grip_press", .95f);
    release = p.getFloat("grip_release", .90f);
    deadzone = p.getFloat("stick_deadzone", .10f);
  }
  public String host(Context c) {
    return automatic ? wifiGateway(c) : manualHost;
  }
  public static boolean validIpv4(String host) {
    String[] parts = host.split("\\.", -1);
    if (parts.length != 4)
      return false;
    for (String s : parts)
      if (!s.matches("[0-9]{1,3}") || Integer.parseInt(s) > 255)
        return false;
    int first = Integer.parseInt(parts[0]);
    return first > 0 && first < 224 && first != 127;
  }
  public static String wifiGateway(Context c) {
    ConnectivityManager cm = (ConnectivityManager) c.getSystemService(Context.CONNECTIVITY_SERVICE);
    if (cm == null)
      return "";
    for (Network n : cm.getAllNetworks()) {
      NetworkCapabilities caps = cm.getNetworkCapabilities(n);
      LinkProperties lp = cm.getLinkProperties(n);
      if (caps == null || !caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || lp == null)
        continue;
      for (RouteInfo r : lp.getRoutes())
        if (r.isDefaultRoute() && r.getGateway() instanceof Inet4Address) {
          String ip = r.getGateway().getHostAddress();
          if (validIpv4(ip))
            return ip;
        }
    }
    return "";
  }
}
