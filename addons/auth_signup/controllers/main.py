# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import werkzeug
from werkzeug.urls import url_encode

from odoo import http, tools, _
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.home import ensure_db, Home, SIGN_UP_REQUEST_PARAMS, LOGIN_SUCCESSFUL_PARAMS
from odoo.addons.base_setup.controllers.main import BaseSetup
from odoo.exceptions import UserError
from odoo.http import request

import odoo.tools.import_speeddate  ## IMPORT TO APPEND speeddate DIR TO sys.path  
import odoo.tools.speeddate as spdt


_logger = logging.getLogger(__name__)

LOGIN_SUCCESSFUL_PARAMS.add('account_created')

## ADD EXCEPTION CLASS FOR AGE VALIDATION ON ANY Sign up
class UnderageError(Exception):
    pass

## ADD EXCEPTION FOR ATTENDEE Gender/Decade NOT MATCHING Sign up FOR Event
class AttendeeGenderDecadeError(Exception):
    pass

class AuthSignupHome(Home):

    @http.route()
    def web_login(self, *args, **kw):
        ensure_db()
        response = super().web_login(*args, **kw)
        response.qcontext.update(self.get_auth_signup_config())
        if request.session.uid:
            if request.httprequest.method == 'GET' and request.params.get('redirect'):
                # Redirect if already logged in and redirect param is present
                return request.redirect(request.params.get('redirect'))
            # Add message for non-internal user account without redirect if account was just created
            if response.location == '/web/login_successful' and kw.get('confirm_password'):
                return request.redirect_query('/web/login_successful', query={'account_created': True})
        return response

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext() ## kw HAS NEEDED VALUES

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)
                # Send an account creation confirmation email
                User = request.env['res.users']
                user_sudo = User.sudo().search(
                    User._get_login_domain(qcontext.get('login')), order=User._get_login_order(), limit=1
                )
                template = request.env.ref('auth_signup.mail_template_user_signup_account_created', raise_if_not_found=False)
                if user_sudo and template:
                    template.sudo().send_mail(user_sudo.id, force_send=True)
                return self.web_login(*args, **kw)
            except UserError as e:
                qcontext['error'] = e.args[0]
            except (SignupError, AssertionError) as e:
                if request.env["res.users"].sudo().search([("login", "=", qcontext.get("login"))]):
                    qcontext["error"] = _("Another user is already registered using this email address.")
                else:
                    _logger.warning("%s", e)
                    qcontext['error'] = _("Could not create a new account.") + "\n" + str(e)
            ## CATCH UnderageError
            except UnderageError as e:
                ## WANT REDIRECT INSTEAD OF EndOfPage MESSAGE
                return request.redirect('/sign-up-failure')
            except AttendeeGenderDecadeError as e:
                qcontext['error'] = e.args[0]
                ## MUST CLEAR CART -- SAME CODE AS /shop/cart/clear
                spdt.clear_cart()

                return request.redirect('/event?registration_msg=Gender_settings_or_Birthdate_did_not_match_event')

            
        elif 'signup_email' in qcontext and qcontext.get('signup_email') != "edlevene@hotmail.com":  ## and user NOT Admin
            user = request.env['res.users'].sudo().search([('email', '=', qcontext.get('signup_email')), ('state', '!=', 'new')], limit=1)
            if user:
                ## DON'T WANT TO GO TO /my ACCOUNT PAGE: return request.redirect('/web/login?%s' % url_encode({'login': user.login, 'redirect': '/web'}))
                ## MAKE redirect CONDITIONAL ON predirect PARAM
                predirect = request.params.get('redirect')
                if predirect == '/shop/cart':
                    return request.redirect('/shop/cart')
                else:
                    return request.redirect('/sign-up-success')

        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @http.route('/web/reset_password', type='http', auth='public', website=True, sitemap=False)
    def web_auth_reset_password(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('reset_password_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                if qcontext.get('token'):
                    self.do_signup(qcontext)
                    return self.web_login(*args, **kw)
                else:
                    login = qcontext.get('login')
                    assert login, _("No login provided.")
                    _logger.info(
                        "Password reset attempt for <%s> by user <%s> from %s",
                        login, request.env.user.login, request.httprequest.remote_addr)
                    request.env['res.users'].sudo().reset_password(login)
                    qcontext['message'] = _("Password reset instructions sent to your email")
            except UserError as e:
                qcontext['error'] = e.args[0]
            except SignupError:
                qcontext['error'] = _("Could not reset your password")
                _logger.exception('error when resetting password')
            except Exception as e:
                qcontext['error'] = str(e)

        elif 'signup_email' in qcontext:
            user = request.env['res.users'].sudo().search([('email', '=', qcontext.get('signup_email')), ('state', '!=', 'new')], limit=1)
            if user:
                return request.redirect('/web/login?%s' % url_encode({'login': user.login, 'redirect': '/web'}))

        response = request.render('auth_signup.reset_password', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response
    
    def get_auth_signup_config(self):
        """retrieve the module config (which features are enabled) for the login page"""

        def my_get_current_user():
            """ return login/email for currently logged in user """
            session_info = request.env['ir.http'].session_info()
            return session_info.get('username')
        
        get_param = request.env['ir.config_parameter'].sudo().get_param

        ## FIND LOGGED-IN USER login/email AND PERSIST FOR qcontext update
        login = my_get_current_user()

        return {
            'disable_database_manager': not tools.config['list_db'],
            'signup_enabled': request.env['res.users']._get_signup_invitation_scope() == 'b2c',
            'reset_password_enabled': get_param('auth_signup.reset_password') == 'True',
            'signup_email': login
        }

    def get_auth_signup_qcontext(self):
        """ Shared helper returning the rendering context for signup and reset password """
        qcontext = {k: v for (k, v) in request.params.items() if k in SIGN_UP_REQUEST_PARAMS}
        qcontext.update(self.get_auth_signup_config())
        if not qcontext.get('token') and request.session.get('auth_signup_token'):
            qcontext['token'] = request.session.get('auth_signup_token')
        if qcontext.get('token'):
            try:
                # retrieve the user info (name, login or email) corresponding to a signup token
                token_infos = request.env['res.partner'].sudo().signup_retrieve_info(qcontext.get('token'))
                for k, v in token_infos.items():
                    qcontext.setdefault(k, v)
            except:
                qcontext['error'] = _("Invalid signup token")
                qcontext['invalid_token'] = True
        return qcontext

    def _prepare_signup_values(self, qcontext):
        # values = { key: qcontext.get(key) for key in ('login', 'name', 'password') }
        ## ADDITIONAL FIELDS
        values = { key: qcontext.get(key) for key in ('login', 'mobile', 'name', 'password', 'fname', 'birthdate', 'city', 'state_id', 'zip', 
            'gender', 'gender_pref_female', 'gender_pref_male', 'gender_pref_alt','how_hear', 'hobbies', 'charities') }
        if not values:
            raise UserError(_("The form was not properly filled in."))
        if values.get('password') != qcontext.get('confirm_password'):
            raise UserError(_("Passwords do not match; please retype them."))
        supported_lang_codes = [code for code, _ in request.env['res.lang'].get_installed()]
        lang = request.context.get('lang', '')
        if lang in supported_lang_codes:
            values['lang'] = lang
            
        ## CONVERT city TO UPPERCASE
        values['city'] = values.get('city').upper()

        ## A LIKELY PLACE TO VALIDATE/FLAG birthdate FOR UNDER 21
        ## CALC AGE FROM birthdate
        age = spdt.calc_age(values['birthdate'])

        ## RAISE UNDER-AGE ERROR
        if age < 21:
            qcontext['error'] = _("Your Birthdate is invalid - not eligible for a new account.")
            raise UnderageError(_("Your Birthdate is invalid - too young for a new account."))

        ## CONCATENTATE fname + name FOR FULL NAME ???
        ## values['name'] = values.get('fname') + ' ' + values.get('name')

        ## CALL fail_checks_for_attendee_at_event() SEPERATELY, FOR USER WHO JUST DID 'Sign up'
        event_name = request.params.get('event')
        _logger.info("## ## ## event name:%s", event_name)
        ## NOW MAYBE MAKE THAT VALIDATION CALL
        qcontext['error'] = None
        if event_name:
            failures = spdt.fail_checks_for_attendee_at_event(values['gender'], values['gender_pref_female'], values['gender_pref_male'], values['birthdate'], event_name)
            if failures:
                ### WILL LATER raise AttendeeGenderDecadeError(_("%s did not match event", failures))
                qcontext['error'] = failures + " did not match event"
        
        return values

    def do_signup(self, qcontext):
        """ Shared helper that creates a res.partner out of a token """
        values = self._prepare_signup_values(qcontext)
        self._signup_with_values(qcontext.get('token'), values)
        request.env.cr.commit()
        ## *AFTER* Sign up IS COMMITTED, CHECK qcontext AND RAISE ASSUMED ERROR
        try:
            if qcontext['error']:
                _logger.info("## ## ## sensing qcontext error, assuming AttendeeGenderDecadeError")
                raise AttendeeGenderDecadeError(_(qcontext['error']))
        except KeyError:
            pass

    def _signup_with_values(self, token, values):
        login, password = request.env['res.users'].sudo().signup(values, token)
        request.env.cr.commit()     # as authenticate will use its own cursor we need to commit the current transaction
        pre_uid = request.session.authenticate(request.db, login, password)
        if not pre_uid:
            raise SignupError(_('Authentication Failed.'))

class AuthBaseSetup(BaseSetup):
    @http.route()
    def base_setup_data(self, **kwargs):
        res = super().base_setup_data(**kwargs)
        res.update({'resend_invitation': True})
        return res
