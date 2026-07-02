import {useAppDispatch, useAppSelector} from "../../app/store.ts";
import {selectAuthIsLoading, selectIsLoggedIn} from "./authSlice.ts";
import {useEffect} from "react";
import {logIn} from "./authMiddleware.ts";
import {WithReactChildren} from "../../types/common.ts";

type WithAuthRequiredProps = WithReactChildren

const WithAuthRequired = ({children}: WithAuthRequiredProps) => {
    const loggedIn = useAppSelector(selectIsLoggedIn)
    const loading = useAppSelector(selectAuthIsLoading)

    const dispatch = useAppDispatch();

    useEffect(() => {
        if (!loggedIn && !loading) {
            const path = typeof window !== "undefined"
                ? `${window.location.pathname}${window.location.search}${window.location.hash}`
                : undefined;
            dispatch(logIn(path))
        }
    }, [loggedIn, loading, dispatch]);

    if (!loggedIn || loading) return null;

    return (
        <>{children}</>
    )
}

export default WithAuthRequired;
