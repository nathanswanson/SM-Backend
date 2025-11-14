# create a dev admin


from server_manager.webservice.util.data_access import DB


def dev_startup():
    """Create a dev admin user if in dev mode and no users exist"""
    if not DB().lookup_username("admin"):
        # create dev data

        # DB().create_user(
        #     UsersCreate(
        #         id=1,
        #         username="admin",
        #         disabled=False,
        #         admin=True,
        #         hashed_password=get_password_hash("admin"),
        #         scopes=[""],
        #     )
        # )
        pass
