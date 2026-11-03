# Sevbify's release build is shrunk and optimised by R8 (Compose and the media player run noticeably smoother
# that way). Its own code is kept as it is (the phone-side Python and the media service reach into it by name),
# so only the libraries are optimised.
-keep class com.sevbify.app.** { *; }
-keep class com.chaquo.python.** { *; }
-keepattributes *Annotation*, Signature, InnerClasses, EnclosingMethod, SourceFile, LineNumberTable
-ignorewarnings
