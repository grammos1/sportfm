import sys
import vlc
import datetime
from time import sleep
from pydub import AudioSegment
import owncloud
import paramiko
import os
import urllib.request
import configparser
import sys
import shutil

def getSetting(section, setting):
    config = configparser.ConfigParser()
    config.read('settings.cfg')
    if section not in config.sections():
       # print("Section " + section + " not found. Will try DEFAULT")
        section = "DEFAULT"
    try:
        #print ("Setting " + setting + " to " + config[section][setting])
        return config[section][setting]
    except:
        print ("Key " + setting + " not found in section "+ section)

name = ""
duration = -1
toOwncloud = False
toPodcast = False
toLocal = False

if len (sys.argv) <2:
    print ("You have not passed enough arguments")
    print ("Usage: pyrcord [name=NAME] duration=DURATION_IN_SECONDS [toOwncloud] [toPodcast] [toLocal]")

    exit (1)
for param in sys.argv:
    #print (param)
    if "name" in str(param).lower():
        #print ("Found Name : " +  str(param).lower().strip("name="))
        name = str(param).lower().strip("name=")
    if "duration" in str(param).lower():
        #print ("Found Duration of "+  str(param).lower().strip("duration="))
        try:
            duration = int(str(param).lower().strip("duration="))
        except:
            print ("Duration must be a number, eg duration=3660")
            print("Usage: pyrcord [name=NAME] duration=DURATION_IN_SECONDS [toOwncloud] [toPodcast] [toLocal]")
            exit(1)
    if "toowncloud" in str(param).lower():
        #print("Will upload to ouwncloud")
        toOwncloud=True
    if "topodcast" in str(param).lower():
        #print("Will upload to podcast")
        toPodcast = True
    if "tolocal" in str(param).lower():
        #print("Will upload to podcast")
        toLocal = True
if name=="":
    print ("You must specify a name, e.g. name=myShow")
    print ("Usage: pyrcord [name=NAME] duration=DURATION_IN_SECONDS [toOwncloud] [toPodcast] [toLocal]")
    exit(1)

if duration <=0 :
    print ("I do need the duration of the clip you want me to record. Don't make me guess ...")
    print ("Usage: pyrcord name=NAME duration=DURATION_IN_SECONDS [toOwncloud] [toPodcast] [toLocal]")
    exit (1)

#stream = 'http://sportfm.live24.gr/sportfm7712'
stream = ""
ocuser= ""
ocpass = ""
ocurl = ""
ocbasedir = ""
sshuser = ""
sshpass = ""
sshserver = ""
sshpath = ""
podcastrefreshurl=""
trimstart = 0
savelocation = ""

stream = getSetting(name.upper(),"stream")
if stream=="":
    print ("Cannot determine stream url. Set the stream parameter in the settings file. Goodbye")
    exit (1)
if toOwncloud:
    ocuser = getSetting("OWNCLOUD", "user")
    ocpass = getSetting("OWNCLOUD", "password")
    ocurl = getSetting("OWNCLOUD", "url")
    ocbasedir = getSetting("OWNCLOUD", "ocbasedir")
    if ocuser == "" or ocpass=="" or ocurl == "":
        print ("You want to upload to owncloud but owncloud settings in the config file are incomplete")
        print ("Set the user, password, url and ocbasedir key/values")
        print ("Good bye")
        exit (1)

if toPodcast:
    sshuser = getSetting(name.upper(),"user")
    sshpass = getSetting(name.upper(),"password")
    sshserver = getSetting(name.upper(),"server")
    sshpath = getSetting(name.upper(),"podcastpath")
    podcastrefreshurl = getSetting(name.upper(), "podcastrefreshurl")
    if sshuser=="" or sshpass=="" or sshserver=="" or podcastrefreshurl=="":
        print("You want to upload to podcast generator but settings in the config file are incomplete")
        print ("Set the user, password, server, podcastpath and podcastrefreshurl key/values")
        print ("Good bye")
if toLocal:
    savelocation = getSetting("DEFAULT", "saveto")
    if savelocation=="":
        print ("You want to save the file to local/mounted filesystems but settings in the config file are incomplete")
        print ("Please set the savelocation key/value under the DEFAULT section")
        print ("Good bye")
        exit (1)
    print("Will save to " + str(savelocation))

trimstart = int(getSetting(name.upper(),"trimstart"))
recordatleast = duration
reduceby = trimstart #seconds to slice off the beginning

now = datetime.datetime.now()
end = now + datetime.timedelta(seconds=recordatleast)
today = now.isoformat()
today = str(today[:10]).replace("-","")
today = today[2:]
today = today +"-"+ now.strftime('%a')
streamName = name
filename = streamName + today + ".mp3"
targetdir = "/" + streamName +"/" + str(now.year) + "/" + str(now.month) + " - " + str(now.strftime("%b"))
print ("Starting at " + str(now))
print ("Will stop at " + str(end))
parameters = "sout=#transcode{acodec=mp3,channels=2,ab=64}:duplicate{dst=std{access=file,mux=raw,dst='"+filename+"'"

oclocation = ocbasedir+ targetdir + "/"



instance = vlc.Instance()
player = instance.media_player_new()
media = instance.media_new(stream, parameters)
media.get_mrl()
player.set_media(media)
try:
    player.play()
except:
    print ("Cannot record from that stream")
    print ("/OpensWindowAndJumpsOut")
    exit (2)
recording = True
while recording:
    now = datetime.datetime.now()
    if str(player.get_state()) == "State.Ended":
        print ("Cannot record from that stream or connection lost")
        break
    if now > end:
        player.stop()
        print ("OK. We are done recording")
        break

try:
    recording = AudioSegment.from_mp3(filename)
except:
    print ("Failed to record a valid audio file")
    print("/OpensWindowAndJumpsOut")
    exit (2)
recording = recording[reduceby*1000:]
recording = recording +6
title = filename.replace(".mp3", "")
print ("Adding Title " + title)
artist = streamName
genre = "radio"
album = streamName
tags = {'title': title, 'artist': artist, 'genre' : genre, 'album' : album}
recording.export("new" + filename, format="mp3", bitrate="64k", tags=tags)

if toOwncloud:
    print ("Uploading to OwnCloud")
    oc = owncloud.Client(ocurl)
    oc.login(ocuser, ocpass)
    dirs = oclocation.split("/")
    dirtocreate = ""
    for x in dirs:
        dirtocreate = dirtocreate + x + "/"
        try:
            oc.mkdir(dirtocreate)
        except:
            print ("Cannot create OwnCloud Dir, possibly because it exists already")

    try:
        oc.put_file(oclocation + filename, "new"+filename)
    except:
        print ("Could not upload file. Go figure ...")

if toPodcast:
    print ("Uploading file to podcasr")
    ssh = paramiko.SSHClient()
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
    ssh.connect(sshserver, username=sshuser, password=sshpass)
    sftp = ssh.open_sftp()
    sftp.put("new"+filename, sshpath + filename)
    sftp.close()
    ssh.close()

    print ("Refreshing Podcasts")
    contents = urllib.request.urlopen(podcastrefreshurl).read()
if toLocal:
    print ("Saving to local location")
    print ("will make dir " + savelocation + targetdir)
    try:
        os.makedirs(savelocation + targetdir)
    except:
        print ("Could not create local dir, possibly because it exists")
    try:
        shutil.copy2 ("new" + filename, savelocation + targetdir+"/"+filename)
    except:
        print ("Could not copy file")
print ("Deleting local files")

os.remove(filename)
os.remove("new"+filename)

exit(0)




