import pyttsx3

e = pyttsx3.init()
voices = e.getProperty("voices")

# Microsoft Zira = index 1
e.setProperty("voice", voices[1].id)
e.setProperty("rate", 165)
e.setProperty("volume", 1.0)

e.say("Hi, I'm Sally. I'm here to help you with your estimate.")
e.runAndWait()
