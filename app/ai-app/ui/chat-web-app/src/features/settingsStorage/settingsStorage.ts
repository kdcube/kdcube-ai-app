import {sha} from "../../utils/utils.ts";

let defaultStorage: Storage = localStorage;

export const setDefaultParamStorage = (storage: Storage) => {
    defaultStorage = storage;
}

const getKVObjectKey = (user?: string | null) => {
    return `settings_${user ? sha(user) : 'shared'}`;
}

export const writeParam = (key: string, value: unknown, user?: string | null, storage?: Storage | null) => {
    storage = storage || defaultStorage;
    const kvObjectKey = getKVObjectKey(user);
    const kvObjectValue = storage.getItem(kvObjectKey);
    let kvObject: Record<string, unknown>
    if (kvObjectValue) {
        try {
            kvObject = JSON.parse(kvObjectValue);
        } catch (e) {
            console.error(`Unable to parse settings string. Dropping ${kvObjectKey}`, e);
            kvObject = {}
        }
    } else {
        kvObject = {};
    }
    kvObject[key] = value;
    try {
        storage.setItem(kvObjectKey, JSON.stringify(kvObject));
    } catch (e) {
        console.error("Unable to write param (is it serializable?)", e);
    }

}

export const readParam = (key: string, defaultValue?: unknown, user?: string | null, storage?: Storage | null): unknown => {
    storage = storage || defaultStorage;
    const kvObjectKey = getKVObjectKey(user);
    const kvObjectValue = storage.getItem(kvObjectKey);
    if (!kvObjectValue) {
        return defaultValue;
    }
    try {
        return JSON.parse(kvObjectValue)[key]
    } catch (e) {
        console.error(`Unable to parse settings string. Dropping ${kvObjectKey}`, e);
        storage.removeItem(kvObjectKey);
        return defaultValue;
    }
}

export const dropParam = (key: string, user?: string | null, storage?: Storage | null) => {
    storage = storage || defaultStorage;
    const kvObjectKey = getKVObjectKey(user);
    const kvObjectValue = storage.getItem(kvObjectKey);
    if (!kvObjectValue) {
        return;
    }
    try {
        const kvObject = JSON.parse(kvObjectValue)
        delete kvObject[key]
        storage.setItem(kvObjectKey, JSON.stringify(kvObject));
    } catch (e) {
        console.error(`Unable to parse settings string. Dropping ${kvObjectKey}`, e);
        storage.removeItem(kvObjectKey);
        return undefined;
    }
}

