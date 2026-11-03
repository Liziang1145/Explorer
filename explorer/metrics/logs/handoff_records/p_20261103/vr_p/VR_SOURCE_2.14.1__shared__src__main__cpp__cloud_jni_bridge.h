// Including translation unit supplies cloudHandle(), cloudHead(), cloudRecenter().
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_cloud_CloudNative_configure(JNIEnv* e, jclass, jlong generation, jobjectArray ids,
                                                                                jfloatArray boxes) {
  int n = e->GetArrayLength(ids);
  if (n > 30000 || e->GetArrayLength(boxes) != n * 6) return;
  std::vector<float> b(n * 6);
  e->GetFloatArrayRegion(boxes, 0, b.size(), b.data());
  std::vector<cloud::Meta> meta;
  for (int i = 0; i < n; i++) {
    jstring id    = (jstring)e->GetObjectArrayElement(ids, i);
    const char* s = e->GetStringUTFChars(id, nullptr);
    cloud::Meta m;
    m.id = s;
    std::copy_n(b.data() + i * 6, 6, m.bounds.begin());
    meta.push_back(std::move(m));
    e->ReleaseStringUTFChars(id, s);
    e->DeleteLocalRef(id);
  }
  auto gpu = cloudHandle();
  if (gpu) gpu->configure(generation, std::move(meta));
}
extern "C" JNIEXPORT jboolean JNICALL Java_com_tanluzhe_cloud_CloudNative_offer(JNIEnv* e, jclass, jlong generation, jstring id, jobject buffer,
                                                                                jboolean coarse) {
  try {
    auto raw  = (const uint8_t*)e->GetDirectBufferAddress(buffer);
    auto size = e->GetDirectBufferCapacity(buffer);
    if (size <= 0) return false;
    auto points     = cloud::packedPoints(raw, size);
    const char* s   = e->GetStringUTFChars(id, nullptr);
    std::string key = s;
    e->ReleaseStringUTFChars(id, s);
    auto gpu = cloudHandle();
    return gpu && gpu->offerPacked(generation, std::move(key), std::move(points), coarse);
  } catch (const std::exception&) {
    return false;
  }
}
extern "C" JNIEXPORT jobjectArray JNICALL Java_com_tanluzhe_cloud_CloudNative_resident(JNIEnv* e, jclass, jlong generation) {
  auto gpu    = cloudHandle();
  auto ids    = gpu ? gpu->resident(generation) : std::set<std::string>{};
  jclass cls  = e->FindClass("java/lang/String");
  auto result = e->NewObjectArray(ids.size(), cls, nullptr);
  int i       = 0;
  for (const auto& id : ids) {
    jstring s = e->NewStringUTF(id.c_str());
    e->SetObjectArrayElement(result, i++, s);
    e->DeleteLocalRef(s);
  }
  e->DeleteLocalRef(cls);
  return result;
}
extern "C" JNIEXPORT jobjectArray JNICALL Java_com_tanluzhe_cloud_CloudNative_pending(JNIEnv* e, jclass, jlong generation) {
  auto gpu    = cloudHandle();
  auto ids    = gpu ? gpu->queuedIds(generation) : std::set<std::string>{};
  jclass cls  = e->FindClass("java/lang/String");
  auto result = e->NewObjectArray(ids.size(), cls, nullptr);
  int i       = 0;
  for (const auto& id : ids) {
    jstring s = e->NewStringUTF(id.c_str());
    e->SetObjectArrayElement(result, i++, s);
    e->DeleteLocalRef(s);
  }
  e->DeleteLocalRef(cls);
  return result;
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_cloud_CloudNative_retain(JNIEnv* e, jclass, jlong gen, jobjectArray ids) {
  std::set<std::string> keep;
  int n = e->GetArrayLength(ids);
  for (int i = 0; i < n; i++) {
    jstring s     = (jstring)e->GetObjectArrayElement(ids, i);
    const char* v = e->GetStringUTFChars(s, nullptr);
    keep.insert(v);
    e->ReleaseStringUTFChars(s, v);
    e->DeleteLocalRef(s);
  }
  auto gpu = cloudHandle();
  if (gpu) gpu->retain(gen, std::move(keep));
}
extern "C" JNIEXPORT jlongArray JNICALL Java_com_tanluzhe_cloud_CloudNative_stats(JNIEnv* e, jclass) {
  jlong values[8]{};
  auto gpu = cloudHandle();
  if (gpu)
    for (int i = 0; i < 8; i++) values[i] = gpu->stats[i].load();
  auto out = e->NewLongArray(8);
  e->SetLongArrayRegion(out, 0, 8, values);
  return out;
}
extern "C" JNIEXPORT jfloatArray JNICALL Java_com_tanluzhe_cloud_CloudNative_head(JNIEnv* e, jclass) {
  auto p   = cloudHead();
  auto out = e->NewFloatArray(3);
  e->SetFloatArrayRegion(out, 0, 3, p.data());
  return out;
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_cloud_CloudNative_recenter(JNIEnv*, jclass, jfloat floorY) {
  if (std::isfinite(floorY)) cloudRecenter(floorY);
}

extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_cloud_CloudNative_policy(JNIEnv*, jclass, jlong gen, jfloat radius) {
  auto gpu = cloudHandle();
  if (gpu) gpu->policy(gen, radius);
}
extern "C" JNIEXPORT void JNICALL Java_com_tanluzhe_cloud_CloudNative_grid(JNIEnv* e, jclass, jlong gen, jfloat meters, jintArray array) {
  int n = e->GetArrayLength(array);
  if (n > 90000 || n % 3) return;
  std::vector<int> cells(n);
  if (n) e->GetIntArrayRegion(array, 0, n, cells.data());
  auto gpu = cloudHandle();
  if (gpu) gpu->grid(gen, meters, std::move(cells));
}

extern "C" JNIEXPORT jfloatArray JNICALL Java_com_tanluzhe_cloud_CloudNative_anchor(JNIEnv* e, jclass) {
  auto matrix = cloudAnchor();
  auto out    = e->NewFloatArray(16);
  e->SetFloatArrayRegion(out, 0, 16, matrix.data());
  return out;
}
