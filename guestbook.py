import datetime
import logging
import os
import urllib

from google.appengine.api import search, taskqueue
from google.appengine.datastore.datastore_v4_pb import GqlQuery
from google.appengine.ext import blobstore, db, ndb
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import images
import webapp2
import json
import random
from google.appengine.api import memcache


def insertitem(latitude, longitude, passcode, index):
    my_document = search.Document(
    # Setting the doc_id is optional. If omitted, the search service will create an identifier.
    fields=[
       search.TextField(name='passcode', value=passcode),
       search.GeoField(name='location', value=search.GeoPoint(float(latitude), float(longitude)))
       ])
    try:
        index = search.Index(name=index)
        results = index.put(my_document)
        return results[0].id
    except search.Error:
        logging.exception('Put failed')
    
    
        #else return success

def searchitem(latitude, longitude, passcode, index):
    index = search.Index(name=index)
    if index:
        query_string = "passcode='%s' AND distance(location, geopoint(%s, %s)) < 500" % (passcode,latitude, longitude)
        result = index.search(query_string)
        if result:
            if(result.number_found > 0):
                list_of_documents = result.results
                return list_of_documents
#                 lMyDocument = list_of_documents[0]
#                 return lMyDocument.doc_id
            else:
                return 0;
        else:
            return 0;

def getpublicpass(latitude, longitude):
    index = search.Index(name="public")
    if index:
        query_string = "distance(location, geopoint(%s, %s)) < 500" % (latitude, longitude)
        result = index.search(query_string)
        if result:
            if(result.number_found > 0):
                list_of_documents = result.results
                return list_of_documents
            else:
                return 0;
        else:
            return 0;

class Picture(db.Model):
    search_document_id = db.StringProperty()
    blob_key = db.StringProperty()
    blob_size = db.StringProperty()
    username = db.StringProperty()
    passcode = db.StringProperty()
#     location = db.GeoPtProperty()

class Counter(db.Model):
    total_entries = db.IntegerProperty()
    pics_from_gallery = db.IntegerProperty()
    pics_from_camera = db.IntegerProperty()
    img_size_small = db.IntegerProperty()
    img_size_med = db.IntegerProperty()
    img_size_orig = db.IntegerProperty()

class CounterEnty(db.Model):
    user_name = db.StringProperty()
    password = db.StringProperty()
    picsource = db.StringProperty()
    pic_size = db.StringProperty()


class MainHandler(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload')
        self.response.out.write('<html><body><p>Welcome To My Site</p></body></html>')
        self.response.out.write('<form action="%s" method="POST" enctype="multipart/form-data">' % upload_url)
        self.response.out.write("""Upload File: <input type="file" name="uploaded_file"><br>
        Passcode : <input type="text" name="passcode"> <br> 
        lat : <input type="text" name="latitude"> lon: <input type="text" name="longitude"> <br> 
        username <input type="text" name="username"><br> 
        picsouce(gallery or camera) <input type="text" name="picsource"><br>
        imagesize 25 or 50 or 100 <input type="text" name="imagesize"><br>
        <input type="submit" name="submit" value="Submit"> </form></body></html>""")

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('uploaded_file')  # 'file' is file upload field in the form
        blob_info = upload_files[0]
        var_tuple = self.request.POST
        if 'passcode' and 'latitude' and 'longitude' and 'username' and 'imagesize' and 'picsource' in var_tuple:
            passcode = var_tuple['passcode']
            username = var_tuple['username']
            latitude = var_tuple['latitude']
            longitude = var_tuple['longitude']
            passcodeStr = str(passcode)
            if passcodeStr.startswith("#",0,len(passcodeStr)):
                doc_id = insertitem(latitude, longitude, passcode,"public")
            else:
                doc_id = insertitem(latitude, longitude, passcode,"private")
            p = Picture()
            p.search_document_id = doc_id
            p.blob_key = str(blob_info.key())
            p.blob_size = str(blob_info.size)
            p.username = username
            p.passcode = passcode
            p.save()
            imagesize = var_tuple['imagesize']
            picsource = var_tuple['picsource']
            increment(picsource)
            increment(imagesize)
#                 lCounterEntry = CounterEnty()
#                 lCounterEntry.user_name = username
#                 lCounterEntry.password = passcode
#                 lCounterEntry.picsource = picsource
#                 lCounterEntry.pic_size = imagesize
#                 lCounterEntry.save()
            
            # Add the task to the default queue. to delete the picture after 10 mins.    // 3 mins for testing
            taskqueue.add(url='/worker', countdown= 86400 ,params={'search_document_id': doc_id})
            self.response.out.write("File Uploaded Successfully blobkey:[%s]" % blob_info.key())
            self.response.out.write("savedkey: [%s]" % str(blob_info.key()))
            self.response.out.write("passcode: [%s]" % str(passcode))
            self.response.out.write("latitude: [%s]" % str(latitude))
            self.response.out.write("longitude: [%s]" % str(longitude))
            self.response.out.write("document search : [%s]" % str(p.search_document_id))
        else:
            self.response.out.write("ERROR in variables sent")
        
        
        #maybe here we can return the address
#         self.response.out.write("contents[%s]" % str(ss))    
#         self.redirect('/serve/%s' % blob_info.key())

class GetStats(webapp2.RequestHandler):
    def get(self):
        self.response.out.write( "image size small %s , med %s , original %s --- camera pics %s , gallery pics %s" %(str(get_count("25")),
                                                                                                   str(get_count("50")),
                                                                                                   str(get_count("100")),
                                                                                                   str(get_count("gallery")),
                                                                                                   str(get_count("camera"))) )
        
class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, resource):
        resource = str(urllib.unquote(resource))
        blob_info = blobstore.BlobInfo.get(resource)
        self.send_blob(blob_info)
        
class UploadUrl(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload')
        self.response.out.write(upload_url)
        
        
class DeletionWorker(webapp2.RequestHandler):
    def post(self): # should run at most 1/s
        search_document_id = self.request.get('search_document_id')
        if search_document_id:
            q = db.GqlQuery("SELECT * FROM Picture " +
                    "WHERE search_document_id = :1 ",
                    search_document_id)
                    # The query is not executed until results are accessed.
            result = q.get()
            if (result):
                picture = result
                if picture:
                    images.delete_serving_url(picture.blob_key)
                    blobstore.delete([picture.blob_key])
                    picture.delete()
                    passcodeStr = str(picture.passcode)
                    if passcodeStr.startswith("#",0,len(passcodeStr)):
                        index = search.Index(name="public")
                        index.delete([search_document_id])
                    else:
                        index = search.Index(name="private")
                        index.delete([search_document_id])
                #TODO: DELETE Search key and document as well from search index

# class CollectStatsWorker(webapp2.RequestHandler):
#     def post(self): # should run at most 1/s
#         counter = Counter.all()
#         if counter.count() > 0:
#             counter = counter.get()
#         else:
#             counter = Counter()
#             counter.total_entries = 0
#             counter.pics_from_gallery = 0
#             counter.pics_from_camera = 0
#             counter.img_size_small = 0
#             counter.img_size_med = 0
#             counter.img_size_orig = 0
#         counter.save()
        
#         allCounterEntries = CounterEnty.all()
#         if(allCounterEntries.count() > 0):
#             counter.total_entries = counter.total_entries + allCounterEntries.count()
#             camerapics = allCounterEntries.filter('picsource =', 'camera')
#             counter.pics_from_camera += len(camerapics)
#             gallerypics = allCounterEntries.filter('picsource =', 'gallery')        
#             counter.pics_from_gallery += len(gallerypics)
#             smallpics = allCounterEntries.filter('pic_size =', '25')        
#             counter.img_size_small += len(smallpics)
#             medpics = allCounterEntries.filter('pic_size =', '50')        
#             counter.img_size_med += len(medpics)
#             origpics = allCounterEntries.filter('pic_size =', '100')        
#             counter.img_size_orig += len(origpics)
#             
#             for entry in allCounterEntries:
#                 entry.delete()
#                 
#             counter.save()
         
class Download(webapp2.RequestHandler):
    def get(self):
        var_tuple = self.request.GET
        if 'passcode' and 'latitude' and 'longitude' in var_tuple:
            passcode = var_tuple['passcode']
            latitude = var_tuple['latitude']
            longitude = var_tuple['longitude']
            passcodeStr = str(passcode)
            
            if passcodeStr.startswith("#",0,len(passcodeStr)):
                result = searchitem(latitude, longitude, passcode, "public")
            else:
                result = searchitem(latitude, longitude, passcode, "private")
                
            if result == 0: #ERROR
                self.response.out.write('5002')
            else:
                #Result has a list of documents
                response = {}
                temp_item = {}
                urls_list = []
                counter = 0
                total_size = 0
                # LATER ON , TODO , we have to limit the amount of pics indicies returned for performance, limit to 10 pics
                for item in result:
                    temp_item = {}
                    q = db.GqlQuery("SELECT * FROM Picture " +
                    "WHERE search_document_id = :1 ",
                    item.doc_id)
                    # The query is not executed until results are accessed.
                    p = q.get()
                    temp_item['no']= counter
                    temp_item['size'] = int(p.blob_size)
                    temp_item['url'] = ("""http://hezzapp.appspot.com/serve/%s""" %p.blob_key)
                    thumbnail_url = images.get_serving_url(p.blob_key,size=150)
                    temp_item['thumb']=thumbnail_url
                    urls_list.append(temp_item)
                    counter += 1
                    total_size += int(p.blob_size)
                response['counter'] = counter
                response['total_size'] = total_size
                response['list'] = urls_list
                
                self.response.out.write(json.dumps(response))
#                 q = Picture.all()
#                 
#                 result = q.filter("search_document_id =", result)
#                 p = result[0]
#                 p = Picture.get(search_document_id =result)
#                 self.response.out.write('<html><body>')
#                 self.response.out.write("""<a href="http://hezzapp.appspot.com/serve/%s" download="myimage"><p>click here</p></a></body></html>""" %p.blob_key)
#                 self.response.out.write("""http://hezzapp.appspot.com/serve/%s""" %p.blob_key)
        else:
            self.response.out.write("5003") # ERROR in variables sent

class Clearall(webapp2.RequestHandler):
    def get(self):
        """Delete all the docs in the given index."""
        doc_index = search.Index(name="private")
        # looping because get_range by default returns up to 100 documents at a time
        while True:
            # Get a list of documents populating only the doc_id field and extract the ids.
            document_ids = [document.doc_id
                            for document in doc_index.get_range(ids_only=True)]
            if not document_ids:
                break
            # Delete the documents for the given ids from the Index.
            doc_index.delete(document_ids)
            
        doc_index = search.Index(name="public")
        # looping because get_range by default returns up to 100 documents at a time
        while True:
            # Get a list of documents populating only the doc_id field and extract the ids.
            document_ids = [document.doc_id
                            for document in doc_index.get_range(ids_only=True)]
            if not document_ids:
                break
            # Delete the documents for the given ids from the Index.
            doc_index.delete(document_ids)
            
        allpics = Picture.all()
        for p in allpics:
            p.delete()
        allcounter = CounterEnty.all()
        for c in allcounter:
            c.delete()
            
class Thumnail(webapp2.RequestHandler):
    def get(self):
        var_tuple = self.request.GET
        if 'passcode' and 'latitude' and 'longitude' in var_tuple:
            passcode = var_tuple['passcode']
            latitude = var_tuple['latitude']
            longitude = var_tuple['longitude']
            passcodeStr = str(passcode)
            if passcodeStr.startswith("#",0,len(passcodeStr)):
                result = searchitem(latitude, longitude, passcode, "public")
            else:
                result = searchitem(latitude, longitude, passcode, "private")
            if result == 0: #ERROR
                self.response.out.write('5002')
            else:
                #Result has a list of documents
                response = {}
                temp_item = {}
                urls_list = []
                counter = 0
                total_size = 0
                # LATER ON , TODO , we have to limit the amount of pics indicies returned for performance, limit to 10 pics
                for item in result:
                    temp_item = {}
                    q = db.GqlQuery("SELECT * FROM Picture " +
                    "WHERE search_document_id = :1 ",
                    item.doc_id)
                    # The query is not executed until results are accessed.
                    p = q.get()
                    temp_item['no']= counter
                    temp_item['size'] = int(p.blob_size)
                    thumbnail_url = images.get_serving_url(p.blob_key,size=200)
                    temp_item['url'] = thumbnail_url
                    #temp_item['url'] = ("""http://hezzapp.appspot.com/serve/%s""" %p.blob_key)
                    urls_list.append(temp_item)
                    counter += 1
                    total_size += int(p.blob_size)
                response['counter'] = counter
                response['total_size'] = total_size
                response['list'] = urls_list
                
                self.response.out.write(json.dumps(response))
        else:
            self.response.out.write("5003") # ERROR in variables sent
                        
class PublicPassHandler(webapp2.RequestHandler):
    def get(self):
        var_tuple = self.request.GET
        if 'latitude' and 'longitude' in var_tuple:
            latitude = var_tuple['latitude']
            longitude = var_tuple['longitude']
            result = getpublicpass(latitude, longitude)
            
            if result == 0: #ERROR
                self.response.out.write('7002') #no public passcodes available
            else:
                #Result has a list of documents
                response = {}
                
                passcode_list = []
                added_passcodes=[]
                counter = 0
                # LATER ON , TODO , we have to limit the amount of pics indicies returned for performance, limit to 10 pics
                for item in result:
                    temp_item={}
                    item_fields = item.fields
                    for field in item_fields:
                        if field.name == "passcode":
                            pass_value = field.value
                            
                            q = db.GqlQuery("SELECT * FROM Picture " +
                                            "WHERE passcode = :1 ",
                                            pass_value)
                            if q:
                                q_count = q.count()
                                if q_count >0:
                                    temp_item['passcode'] = pass_value
                                    temp_item['count'] = q_count
                                    if temp_item not in passcode_list: 
                                        passcode_list.append(temp_item)
                                        counter += 1
                insertion_sort(passcode_list)
                final_list=[]
                for i in  reversed(passcode_list):
                    final_list.append(i)
                response['counter'] = counter
                response['list'] = final_list
                
                
                self.response.out.write(json.dumps(response))
        else:
            self.response.out.write("7003") # ERROR in variables sent                        
                        
class Intro(webapp2.RequestHandler):
    def get(self):
        #flag + msg
        ret = "0App is Under Maintenance, Please be patient"
        self.response.out.write(ret) # ERROR in variables sent




def insertion_sort(list2):
    for i in range(1, len(list2)):
        save = list2[i]
        j = i
        while j > 0 and list2[j - 1]['count'] > save['count']:
            list2[j] = list2[j - 1]
            j -= 1
        list2[j] = save

############################################################
############################################################
###Sharding Counters
############################################################
############################################################
SHARD_KEY_TEMPLATE = 'shard-{}-{:d}'


class GeneralCounterShardConfig(ndb.Model):
    """Tracks the number of shards for each named counter."""
    num_shards = ndb.IntegerProperty(default=20)

    @classmethod
    def all_keys(cls, name):
        """Returns all possible keys for the counter name given the config.

        Args:
            name: The name of the counter.

        Returns:
            The full list of ndb.Key values corresponding to all the possible
                counter shards that could exist.
        """
        config = cls.get_or_insert(name)
        shard_key_strings = [SHARD_KEY_TEMPLATE.format(name, index)
                             for index in range(config.num_shards)]
        return [ndb.Key(GeneralCounterShard, shard_key_string)
                for shard_key_string in shard_key_strings]


class GeneralCounterShard(ndb.Model):
    """Shards for each named counter."""
    count = ndb.IntegerProperty(default=0)


def get_count(name):
    """Retrieve the value for a given sharded counter.

    Args:
        name: The name of the counter.

    Returns:
        Integer; the cumulative count of all sharded counters for the given
            counter name.
    """
    total = memcache.get(name)
    if total is None:
        total = 0
        all_keys = GeneralCounterShardConfig.all_keys(name)
        for counter in ndb.get_multi(all_keys):
            if counter is not None:
                total += counter.count
        memcache.add(name, total, 60)
    return total


def increment(name):
    """Increment the value for a given sharded counter.

    Args:
        name: The name of the counter.
    """
    config = GeneralCounterShardConfig.get_or_insert(name)
    _increment(name, config.num_shards)


@ndb.transactional
def _increment(name, num_shards):
    """Transactional helper to increment the value for a given sharded counter.

    Also takes a number of shards to determine which shard will be used.

    Args:
        name: The name of the counter.
        num_shards: How many shards to use.
    """
    index = random.randint(0, num_shards - 1)
    shard_key_string = SHARD_KEY_TEMPLATE.format(name, index)
    counter = GeneralCounterShard.get_by_id(shard_key_string)
    if counter is None:
        counter = GeneralCounterShard(id=shard_key_string)
    counter.count += 1
    counter.put()
    # Memcache increment does nothing if the name is not a key in memcache
    memcache.incr(name)


@ndb.transactional
def increase_shards(name, num_shards):
    """Increase the number of shards for a given sharded counter.

    Will never decrease the number of shards.

    Args:
        name: The name of the counter.
        num_shards: How many shards to use.
    """
    config = GeneralCounterShardConfig.get_or_insert(name)
    if config.num_shards < num_shards:
        config.num_shards = num_shards
        config.put()



############################################################
############################################################
# TERMS OF USE AND PRIVACY POLICY

terms="""
<h1>
Website and App Terms of Use and Member Terms
</h1>
<p>
THESE TERMS AND CONDITIONS GOVERN YOUR USE OF THE WEBSITE, www.picshake.ca (THE "SITE") AND THE PICSHAKE APP ("APP") AND YOUR RELATIONSHIP WITH VALYRIA INC. ("WE", "US" OR "VALYRIA INC."). PLEASE READ THEM CAREFULLY AS THEY AFFECT YOUR RIGHTS AND LIABILITIES UNDER THE LAW. IF YOU DO NOT AGREE TO THESE TERMS AND CONDITIONS, PLEASE DO NOT REGISTER AS A MEMBER OR USE THE SITE OR APP. PLEASE ALSO SEE OUR PRIVACY AND DATA PROTECTION POLICY FOR INFORMATION ABOUT HOW WE COLLECT AND USE YOUR PERSONAL DATA.
</p>

<h2>
Introduction
</h2>
<p>
The Site and App allow registered members to contribute photographs, images and other content ("Images") and interact with other registered members and their Images.

These terms will apply to registered members and those who simply view the Site ("you").

By using the Site and App, you agree to be bound by these Terms and Conditions.

You are responsible for ensuring that all persons who access our Site through your internet connection or the App through your smart phone, tablet or other device are aware of these Terms and Conditions, and that they comply with them.

Please note that these terms and conditions may be amended from time to time. Notification of any changes will be made via the e-mail address provided by you on registration (if applicable) or by us posting new terms onto the Site and making them available through the App. In continuing to use the Site and App you confirm that you accept the then current terms and conditions in full at the time you use them.
</p>

<h1>
Registration
</h2>
<p>

You can browse the Site without registering but if you wish to contribute Images to the App, leave comments ("Comments") and interact with other members you need to register with us.

When you register as a member we will ask for some of your personal information. Any personal information you provide us with will be handled in accordance with our Privacy and Data Protection Policy which can be seen here.

If you register as a member you will be asked to create a password. In order to prevent fraud, you must keep this password confidential and must not disclose it or share it with anyone. If you know or suspect that someone else knows your password you should notify us by contacting picshake[at]picshake.ca immediately.

If we have reason to believe that there is likely to be a breach of security or misuse of the Site or the App through your account or the use of your password, we may require you to change your password or we may suspend your account. Until you have changed your password or we have reactivated your account you will not be able to access your membership profile.

You agree that all personal information that you supply to us will be accurate, complete and kept up to date at all times. We may use the information provided to us to contact you.

You must be at least 16 years old to register as a member.

We reserve the right the cancel your membership at any time and for any reason including, without limitation, circumstances where you have been reported by other users for uploading inappropriate Images or Comments.
</p>

<h1>
Images and Sharing
</h2>
<p>


The Site and App will enable you to take, upload and share Images. Once taken or uploaded, you will be able share it with other registered members.

Images cannot be exploited, sold, put to any kind of commercial use or transfer of rights without the express consent of the person who captured the picture.

We may remove Images, from the Site or the app for any reason and without notifying you in advance.

By uploading, sharing or publishing any Images on the Site you confirm that:
you took or created the Image;
you own the Image and have not transferred, sold or assigned it to any other person; and 
you own all of the intellectual property rights in the Image.
Any Images that you upload to the app will be your personal responsibility. You will be personally liable for all claims relating to infringement of intellectual property rights, defamation, privacy, breach of contract or any other claim arising from your Images.

You agree to indemnify us in relation to any liability we may suffer as a result of any claims relating to infringement of intellectual property rights, defamation, privacy, breach of contract or any other claim arising from your Images or Comments.

You agree that you will not publish any offensive, inaccurate, misleading, defamatory, fraudulent or illegal Images or Comments.

In particular you agree not to upload using the app(or otherwise use the Site to distribute) any Image or place any Comments on the Site which:
promote racism, bigotry, hatred or physical harm of any kind against any group or individual; 
harasses any person or advocates harassment of any person; 
displays or promotes pornographic or sexually explicit material of any kind; 
do anything or promotes any conduct that is abusive, threatening, obscene, defamatory or libellous;
are illegal, infringe intellectual property rights, defame any person, breach confidentiality or promote any illegal activities;
promote illegal or unauthorized copying of another person's copyright work; 
provide instructive information about illegal activities, such as making or buying illegal weapons, violating someone else's privacy or providing or creating computer viruses;
which involve the transmission of "junk mail", "chain letters"
promote information that you know to be false or misleading; or
contain personal information e.g. names or contact details.

If you would like to remove an image after it has been uploaded, you have to send us an email and we will take the required measures to remove it.

</p>

<h1>
Use and Abuse of the Site
</h2>
<p>


We grant you a limited licence to access and make personal use of the Site and the App, but not to download (other than page caching) or modify it, or any portion of it, except with our express written consent.

If you come across any offensive, inaccurate or damaging Image, Comments or other material on the Site or if you are subject to any form of abuse or harassment we ask that you contact the Site administrator immediately to report the abuse in accordance with our Reporting Policy which can be seen here.

You agree that you will not:
upload any Image or files or post or publish any on the Site that contain viruses, corrupted files, or malicious code or any other similar software or programs that may damage the operation of another's computer. 
access the Site using automated means (such as harvesting bots, robots, spiders, or scrapers) without our permission.
solicit log-in information or access an account belonging to someone else.
bully, intimidate, or harass any user of the Site.
do anything unlawful, misleading, malicious, or discriminatory.
do anything to disable or impair the proper working of the Site, such as a denial of service attack.
do anything to suggest, express or imply that statements made by you are endorsed by us.
impersonate any other person in any profile whether or not that other person is a user of the Site.
directly advertise any goods or services or other business venture with which you are connected without our express written consent.
</p>

<h1>
Viruses, hacking and other offences
</h2>
<p>

You agree not to upload any files or post or publish any on the Site that contain viruses, corrupted files, or malicious code or any other similar software or programs that may damage the operation of another's computer.

You must not misuse our Site by knowingly introducing viruses, trojans, worms, logic bombs or other material which is malicious or technologically harmful. You must not attempt to gain unauthorised access to our Site, the server on which our site is stored or any server, computer or database connected to our site. You must not attack our Site via a denial-of-service attack or a distributed denial-of-service attack.

By breaching this clause 6, you would commit a criminal offence under the Computer Misuse Act 1990. We will report any such breach to the relevant law enforcement authorities and we will co-operate with those authorities by disclosing your identity to them. In the event of such a breach, your membership and right to use our Site will cease immediately.

We will not be liable for any loss or damage caused by viruses, a distributed denial-of-service attack or other technologically harmful material that may infect your computer equipment, computer programs, data or other proprietary material due to your use of our Site or to your downloading of any material posted on it, or on any website linked to it.
</p>

<h1>
Availability of the Site
</h2>
<p>

Although we aim to offer you the best service possible, we make no promise that the services at this Site and app will meet your requirements. We cannot guarantee that the services will be fault-free. If a fault occurs with this Website you should report it to picshake[at]picshake.ca and we will attempt to correct the fault as soon as we reasonably can.

Your access to this Site and app may be occasionally restricted or interrupted to allow for repairs, maintenance or the introduction of new facilities or services. We will attempt to restore the service as soon as we reasonably can. Access to the Site may be restricted whether or not you have registered with us. Any such restrictions or interruptions shall not constitute a breach by us of these terms.
</p>

<h1>
Our Liability
</h2>
<p>

We will operate the Site and App with reasonable skill and care. The services provided do not extend to detailed monitoring or supervision of Images. We do not exercise any editorial control over members or their Images.

The Site and App will contain Images from a variety of members. While we put systems in place to allow members to report offensive, inaccurate, misleading, defamatory, fraudulent or illegal Images or Comments, we do not make any warranties or guarantees in relation to those Images. If we are informed of any such Images we will attempt to remove them as soon as we reasonably can if we believe it is correct to do so. Please see clause 12 below for our 'Notice and Take Down' procedure.

We do not endorse any views or opinions made, shared or published by the members of the Site and App.

We will not be liable for any business, financial, or economic loss nor for any consequential or indirect loss (such as lost reputation, lost profit or lost opportunity) arising as a result of your use of the Site whether such loss is incurred or suffered as a result of our negligence or otherwise. We will not be liable if Images, Comments or other content you have posted and stored on the Site is lost, corrupted or damaged.

Nothing in these terms will limit our liability for fraud or for death or personal injury caused as a result of our negligence.

In the event that you have a dispute with any other member arising from their use of the Site or App, you agree to pursue such claim or action independently of us, and you release us from all claims, liability and damages arising from any such dispute.
</p>

<h1>
Cancellation and Termination
</h2>
<p>


If you wish to cancel your membership you will have to contact us with your username and email. We may require you to confirm your email by sending a link to your email.

We reserve the right to terminate your membership immediately without notice if in our opinion you have breached these terms. In the event of termination, we will delete your member profile and may remove Images which you have placed on the Site/App.
</p>

<h1>
Data Protection Policy
</h2>
<p>

We request that all personal information that you provide is accurate, current and complete.
Any Image published on the Site including sensitive and personal information is publicly available and by posting any such content you are expressly consenting to its public display.

All notices sent to you will be sent to the email address provided with your registration details (as updated by you). By accepting these terms you give your consent to receive communications from us by email and you agree that all agreements, notices, disclosures and other communications that we provide to you by email satisfy any legal requirement that such communications be in writing.

Any personal information that you provide to us in using the Site or as a member will be handled in accordance with our Privacy and Data Protection Policy which can be seen here.

</p>

<h1>
Notice and Take-Down
</h2>
<p>


We will make all reasonable efforts to identify and remove content that is defamatory or infringing on intellectual property rights when notified but cannot be responsible where you have failed to provide the relevant information to enable us to do so.

In the event that you believe that any Images on the Site/App are infringing on intellectual property rights or defamatory you should notify us in writing either by email to picshake[at]picshake.ca .Your notice should include the following information: 
Your full name and contact details, including postal address, telephone number and e-mail address;
The exact place where you uploaded the picture
Some detials and description of the picture.
The reasons that you believe the Image infringes on intellectual property rights or is defamatory;
A statement confirming that you are authorised to act on behalf of the claimant or rights holders; and
A signed declaration of truth in respect of the information in the notice.
Any statement made under this clause 12 may be used in court proceedings.
</p>

<h1>
International Use
</h2>
<p>

We make no promise that materials on this Site are appropriate or available for use in locations outside Canada, and accessing this Site from territories where its contents are illegal or unlawful is prohibited. If you choose to access this site from locations outside Canada, you do so at your own initiative and are responsible for compliance with local laws.

You shall comply with all foreign and local laws and regulations which apply to your use of our Site or our simple randomisation service in whatever country you are physically located, including without limitation, consumer law, export control laws and regulations.
</p>

<h1>
General
</h2>
<p>

If you breach these terms and conditions and we decide to take no action or neglect to do so, then we will still be entitled to take action and enforce our rights and remedies for any other breach.

We will not be responsible for any breach of these terms and conditions caused by circumstances beyond our reasonable control.

We may make changes to the format or content of the Site and App and services provided by us at any time without notice.
"""

privacy="""
<p> 
Privacy and Data Protection Policy

Updated May 30,2014
</p>
<h2>General</h2>
<p>
Valyria Inc. ("we" or "us") take the privacy of your information very seriously. Our Privacy Policy is designed to tell you about our practices regarding the collection, use and disclosure of information that you may provide via the PicShake.ca website (the "Site") or smart phone application (the "App") "PicShake.

By using the Site or App or using any services we offer, you are consenting to the collection, use, and disclosure of that information about you in accordance with, and are agreeing to be bound by, this Privacy Policy.
</p>

<h2>
Ways that we collect information:
</h2>
<p>
We may collect and process the following personal information or data about you and others (information which has been supplied by you as the user of the Site and/or the App and which can be uniquely identified with you or others):

Certain information required to register with our Site, download the App or access other services provided by us, including your first name, last name, email address and date of birth;

Information in relation to your mobile services provider or to your internet services provider which you may communicate to us in the course of using the Site or the App or any of our services;

Your e-mail address and a password to log in to the Site or App;

Photos, video and other content you may upload in the course of using the Site, the App or any services we offer;

Your location;

A record of any correspondence between you and us;

Your replies to any surveys or questionnaires that we may use for research purposes;

Information on your utilisation of the Site and the App and the resources that you access;

Information we may require from you when you report a problem with our Website or our App.

We only collect such information when you choose to supply it to us. You do not have to supply any personal information to us but you may not be able to take advantage of all the services we offer without doing so.

Information is also gathered without you actively providing it, through the use of various technologies and methods such as Internet Protocol (IP) addresses and cookies. These methods do not collect or store personal information.

An IP address is a number assigned to your computer or other device by your Internet Service Provider (ISP), so you can access the Internet. It is generally considered to be non-personally identifiable information, because in most cases an IP address can only be traced back to your ISP or the large company or organisation that provides your internet access (such as your employer if you are at work).

We use your IP address to diagnose problems with our server, report aggregate information, and determine the fastest route for your computer to use in connecting to our site, and to administer and improve the site.
</p>

<h2>
Use and Disclosure:
</h2>
<p>
We may use this information to:

ensure that the content of our Site and the App is presented in the most effective manner for you and for your computer or other internet-enabled device and to customise the Site and the App to your preferences;

assist in making general improvements to the Site and the App;

carry out and administer any obligations arising from any agreements entered into between you and us;

allow you to participate in features of the Site and App;

contact you and notify you about changes to the Site and the App or the services we offer (except where you have asked us not to do this);

analyse how users are making use of our Site and our App for internal marketing and research purposes;

promote our Site, our App and the services we provide, from time to time, subject to permission from the relevant users whose information may be included as part of any promotion.

We do not disclose any information you provide via the Website or the App to any third parties except:

If we are under a duty to disclose or share your personal data in order to comply with any legal obligation (for example, if required to do so by a court order or for the purposes of prevention of fraud or other crime);

in order to enforce any terms of use that apply to our Website and/or App, or to enforce any other terms and conditions or agreements for our services that may apply;

to protect the rights, property, or safety of Valyria Inc., our Site or App users, or any other third parties. This includes exchanging information with other companies and organisations for the purposes of fraud protection and credit risk reduction.

Other than as set out above, we shall not disclose any of your personal information unless you give us permission to do so.
</p>
<h2>
Location Data
</h2>
<p>
The App will make use of location data sent from mobile devices. Your Location is not shown to others and only used internally to send and receive the pictures through the app but we will still collect this data and may use it for our own internal purposes.
</p>

<h2>
Cookies
</h2>
<p>
A cookie is a piece of data stored locally on your computer and internet-enabled device and contains information about your activities on the internet. The information in a cookie does not contain any personally identifiable information you submit via our Site or our App.

We use cookies to track users' progress through the Website, allowing us to make improvements based on usage data. We also use cookies to enable you to remain logged in to that service. A cookie helps you get the best out of the Site and helps us to provide you with a more customised service.

Once you close your browser, our access to the cookie terminates. You have the ability to accept or decline cookies. Most web browsers automatically accept cookies, but you can usually modify your browser setting to decline cookies if you prefer. To change your browser settings you should go to your advanced preferences.

We are required to obtain your consent to use cookies. We have a clear cookies notice on the home page of the Website. If you continue to use the Site having seen the notice then we assume you are happy for us to use the cookies described above.

If you choose not to accept the cookies, this will not affect your access to the majority of information available on our Website. However, you will not be able to make full use of our online services.
</p>
<h2>
Access to and correction of personal information
</h2>
<p>
We will take all reasonable steps in accordance with our legal obligations to update or correct personally identifiable information in our possession that you submit via the Site or the App.

The Act gives you the right to access information held about you. Your right of access can be exercised in accordance with the Act. Any access request may be subject to a fee of $10 to meet our costs in providing you with details of the information we hold about you. If you wish to see details of any personal information that we hold about you please contact us by way of the contact page on our Site.

We take all appropriate steps to protect personally identifiable information in relation to you and others as you transmit such information from your computer or internet-enabled device to our Site and to protect such information for loss, misuse, and unauthorised access, disclosure, alteration, or destruction. We use leading technologies and encryption software to safeguard your data, and operate strict security standards to prevent any unauthorised access to it.

Where you use passwords, usernames, or other special access features on the Site or the App, you also have a responsibility to take reasonable steps to safeguard them.
</p>

<h2>
Access to and correction of personal information
</h2>
<p>
As part of the services offered to you through our Website, the information you provide to us may be transferred to, and stored at, countries outside of Canada. By way of example, this may happen if any of our servers are from time to time located in a country outside of Canada or one of our service providers is located in a country outside of Canada. We may also share information with other equivalent national bodies, which may be located in countries worldwide. These countries may not have similar data protection laws to Canada. If we transfer your information outside of Canada in this way, we will take steps with the aim of ensuring that your privacy rights continue to be protected as outlined in this privacy policy.

If you use our Site while you are outside Canada, your information may be transferred outside Canada in order to provide you with those services.

By submitting your personal information to us you agree to the transfer, storing or processing of your information outside Canada in the manner described above.
</p>
<h2>
Notification of changes to our Privacy Policy
</h2>
<p>
We will notify users of any changes to our Privacy Policy upon logging into the Site and the App to help ensure you are always aware of the information we collect, how we use it, and in what circumstances, if any, we share it with other parties.
</p>
<h2>
Contact us
</h2>
<p>
If at any time you would like to contact us with your views about our privacy practices, or with any enquiry relating to your personal information, you can do so by way of the following email address: picshake@picshake.ca
</p>
"""
        
class Terms(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(terms)
        
class Privacy(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(privacy)
        
app = webapp2.WSGIApplication([('/', MainHandler),
                               ('/upload', UploadHandler),
                               ('/getpic', Download),
                               ('/worker', DeletionWorker),
                               ('/getuploadurl', UploadUrl),
                               ('/getthum', Thumnail),
                               ('/cleanup', Clearall),
                               ('/getintromsg', Intro),
                               ('/getpubpasscodes', PublicPassHandler),
                               ('/getstats', GetStats),
                               ('/terms', Terms),
                               ('/privacy', Privacy),
                               ('/serve/([^/]+)?', ServeHandler)],
                              debug=True)

