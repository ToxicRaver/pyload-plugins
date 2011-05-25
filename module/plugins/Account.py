# -*- coding: utf-8 -*-

"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.
    
    @author: mkaay
"""

from random import choice
from time import time
from traceback import print_exc

from module.utils import compare_time, parseFileSize

class WrongPassword(Exception):
    pass


class Account():
    __name__ = "Account"
    __version__ = "0.2"
    __type__ = "account"
    __description__ = """Account Plugin"""
    __author_name__ = ("mkaay")
    __author_mail__ = ("mkaay@mkaay.de")

    # after that time [in minutes] pyload will relogin the account
    login_timeout = 600
    # account data will be reloaded after this time
    info_threshold = 600


    def __init__(self, manager, accounts):
        self.manager = manager
        self.core = manager.core
        self.accounts = {}
        self.infos = {} # cache for account information
        self.timestamps = {}
        self.setAccounts(accounts)
        self.setup()

    def setup(self):
        pass

    def login(self, user, data, req):
        pass

    def _login(self, user, data):
        req = self.getAccountRequest(user)
        try:
            self.login(user, data, req)
            self.timestamps[user] = time()
        except WrongPassword:
            self.core.log.warning(
                _("Could not login with %(plugin)s account %(user)s | %(msg)s") % {"plugin": self.__name__, "user": user
                                                                                   , "msg": _("Wrong Password")})
            data["valid"] = False

        except Exception, e:
            self.core.log.warning(
                _("Could not login with %(plugin)s account %(user)s | %(msg)s") % {"plugin": self.__name__, "user": user
                                                                                   , "msg": e})
            data["valid"] = False
            if self.core.debug:
                print_exc()
        finally:
            if req: req.close()

    def relogin(self, user):
        req = self.getAccountRequest(user)
        if req:
            req.cj.clear()
            req.close()
        if self.infos.has_key(user):
            del self.infos[user] #delete old information

        self._login(user, self.accounts[user])

    def setAccounts(self, accounts):
        self.accounts = accounts
        for user, data in self.accounts.iteritems():
            self._login(user, data)
            self.infos[user] = {}

    def updateAccounts(self, user, password=None, options={}):
        """ updates account and return true if anything changed """
        
        if self.accounts.has_key(user):
            self.accounts[user]["valid"] = True #do not remove or accounts will not login
            if password:
                self.accounts[user]["password"] = password
                self.relogin(user)
                return True
            if options:
                before = self.accounts[user]["options"]
                self.accounts[user]["options"].update(options)
                return self.accounts[user]["options"] != before
        else:
            self.accounts[user] = {"password": password, "options": options, "valid": True}
            self._login(user, self.accounts[user])
            return True

    def removeAccount(self, user):
        if self.accounts.has_key(user):
            del self.accounts[user]
        if self.infos.has_key(user):
            del self.infos[user]
        if self.timestamps.has_key(user):
            del self.timestamps[user]

    def getAccountInfo(self, name, force=False):
        """ return dict with infos, do not overwrite this method! """
        data = Account.loadAccountInfo(self, name)

        if force or not self.infos.has_key(name):
            self.core.log.debug("Get %s Account Info for %s" % (self.__name__, name))
            req = self.getAccountRequest(name)

            try:
                infos = self.loadAccountInfo(name, req)
                if not type(infos) == dict:
                    raise Exception("Wrong return format")
            except Exception, e:
                infos = {"error": str(e)}

            if req: req.close()

            self.core.log.debug("Account Info: %s" % str(infos))

            infos["timestamp"] = time()
            self.infos[name] = infos
        elif self.infos[name].has_key("timestamp") and self.infos[name]["timestamp"] + self.info_threshold * 60 < time():
            self.scheduleRefresh(name)

        data.update(self.infos[name])
        return data

    def isPremium(self, user):
        info = self.getAccountInfo(user)
        return info["premium"]

    def loadAccountInfo(self, name, req=None):
        return {
            "validuntil": None, # -1 for unlimited
            "login": name,
            #"password": self.accounts[name]["password"], #@XXX: security
            "options": self.accounts[name]["options"],
            "valid": self.accounts[name]["valid"],
            "trafficleft": None, # in kb, -1 for unlimited
            "maxtraffic": None,
            "premium": True, #useful for free accounts
            "timestamp": 0, #time this info was retrieved
            "type": self.__name__,
            }

    def getAllAccounts(self, force=False):
        return [self.getAccountInfo(user, force) for user, data in self.accounts.iteritems()]

    def getAccountRequest(self, user=None):
        if not user:
            user, data = self.selectAccount()
        if not user:
            return None

        req = self.core.requestFactory.getRequest(self.__name__, user)
        return req

    def getAccountCookies(self, user=None):
        if not user:
            user, data = self.selectAccount()
        if not user:
            return None

        cj = self.core.requestFactory.getCookieJar(self.__name__, user)
        return cj

    def getAccountData(self, user):
        return self.accounts[user]

    def selectAccount(self):
        """ returns an valid account name and data"""
        usable = []
        for user, data in self.accounts.iteritems():
            if not data["valid"]: continue

            if data["options"].has_key("time") and data["options"]["time"]:
                time_data = ""
                try:
                    time_data = data["options"]["time"][0]
                    start, end = time_data.split("-")
                    if not compare_time(start.split(":"), end.split(":")):
                        continue
                except:
                    self.core.log.warning(_("Your Time %s has wrong format, use: 1:22-3:44") % time_data)

            if self.infos.has_key(user):
                if self.infos[user].has_key("validuntil"):
                    if self.infos[user]["validuntil"] > 0 and time() > self.infos[user]["validuntil"]:
                        continue
                if self.infos[user].has_key("trafficleft"):
                    if self.infos[user]["trafficleft"] == 0:
                        continue

            usable.append((user, data))

        if not usable: return None, None
        return choice(usable)

    def canUse(self):
        return False if self.selectAccount() == (None, None) else True

    def parseTraffic(self, string): #returns kbyte
        return parseFileSize(string) / 1024

    def wrongPassword(self):
        raise WrongPassword

    def empty(self, user):
        if self.infos.has_key(user):
            self.core.log.warning(_("%(plugin)s Account %(user)s has not enough traffic, checking again in 30min") % {
                "plugin": self.__name__, "user": user})

            self.infos[user].update({"trafficleft": 0})
            self.scheduleRefresh(user, 30 * 60)

    def expired(self, user):
        if self.infos.has_key(user):
            self.core.log.warning(
                _("%(plugin)s Account %(user)s is expired, checking again in 1h") % {"plugin": self.__name__,
                                                                                     "user": user})

            self.infos[user].update({"validuntil": time() - 1})
            self.scheduleRefresh(user, 60 * 60)

    def scheduleRefresh(self, user, time=0, force=True):
        """ add task to refresh account info to sheduler """
        self.core.log.debug("Scheduled Account refresh for %s:%s in %s seconds." % (self.__name__, user, time))
        self.core.scheduler.addJob(time, self.getAccountInfo, [user, force])

    def checkLogin(self, user):
        """ checks if user is still logged in """
        if self.timestamps.has_key(user):
            if self.timestamps[user] + self.login_timeout * 60 < time():
                self.core.log.debug("Reached login timeout for %s:%s" % (self.__name__, user))
                self.relogin(user)
                return False

        return True